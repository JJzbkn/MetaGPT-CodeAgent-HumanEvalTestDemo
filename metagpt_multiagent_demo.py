import argparse
import json
import os
from pathlib import Path
from tqdm import tqdm
import re
import rich
from rich.syntax import Syntax
from rich.console import Console
from rich.panel import Panel

from metagpt.actions import Action, UserRequirement
from metagpt.roles import Role
from metagpt.team import Team
from metagpt.logs import logger
from human_eval.evaluation import evaluate_functional_correctness

data_abs_dir = Path(__file__).parent / "data"
console = Console()

class CodeCompletionAction(Action):
    PROMPT_TEMPLATE: str = '''
    **Role**: You are a software programmer.

    **Task**: As a programmer, you are required to complete the function. Use a Chain-of-Thought approach to break down the problem, create pseudocode, and then write the code in Python language.

    **Instructions**: 
    1. **Understand and Clarify**: Make sure you understand the task. 
    2. **Algorithm/Method Selection**: Decide on the most efficient way. 
    3. **Pseudocode Creation**: Write down the steps you will follow in pseudocode. 
    4. **Code Generation**: Translate your pseudocode into executable Python code.
    NOTE: Generate usable code by this Chain-of-Thought approach without summarizing or providing test cases.

    **Code Formatting**: Please write code in 
    ```python
    {prompt}
    ```
    '''
    name: str = "CodeCompletionAction"
    
    async def run(self, prompt: str):
        rsp = await self._aask(self.PROMPT_TEMPLATE.format(prompt=prompt))
        return rsp

class TestGenerationAction(Action):
    PROMPT_TEMPLATE: str = '''
    **Role**: As a tester, your task is to create basic test cases for the incomplete function.

    **Instructions**: 
    1. Create 2-3 basic test cases that verify the core functionality.
    2. Include at least one edge case test.
    3. Keep the test cases simple and focused.
    NOTE: Generate only the test code section, without creating the specific functions or providing a summary.

    - The format of test cases should be:
    ```python
    assert function_name(input) == expected_output, "Test Case Description"
    ```

    Code to test:
    ```python
    {code}
    ```
    '''
    name: str = "TestGenerationAction"
    
    async def run(self, code: str):
        rsp = await self._aask(self.PROMPT_TEMPLATE.format(code=code))
        return rsp

class CodeReviewerAction(Action):
    PROMPT_TEMPLATE: str = '''
    **Role**: You are a Development Engineer or QA engineer.

    **Task**: Review the code and tests, identify potential issues, and suggest improvements.

    CODE:
    ```python
    {code}
    ```
    TESTS:
    ```python
    {tests}
    ```
    '''
    name: str = "CodeReviewerAction"
    
    async def run(self, code: str, tests: str = ""):
        if tests:
            return await self._aask(self.PROMPT_TEMPLATE.format(code=code, tests=tests))
        else:
            # 如果没有测试用例，只审查代码
            return await self._aask(f"Review this code:\nCODE:\n```python\n{code}\n```")

class Coder(Role):
    name: str = "Coder"
    profile: str = "Coder"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._watch([UserRequirement])
        self.set_actions([CodeCompletionAction])

class Tester(Role):
    name: str = "Tester"
    profile: str = "Tester"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([TestGenerationAction])
        self._watch([CodeCompletionAction])

class Reviewer(Role):
    name: str = "Reviewer"
    profile: str = "Reviewer"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([CodeReviewerAction])
        self._watch([TestGenerationAction])

def extract_code_from_message(message: str) -> str:
    # 首先找到 "### Code Generation" 的位置
    code_gen_pos = message.find("### Code Generation")
    if code_gen_pos == -1:
        return ""
    
    # 从这个位置开始寻找第一个 Python 代码块
    code_start = message.find("```python", code_gen_pos)
    if code_start == -1:
        return ""
    
    # 找到代码块的结束位置
    code_end = message.find("```", code_start + 8)
    if code_end == -1:
        return ""
    
    # 提取代码内容（去掉 ```python 和 结尾的 ```）
    # 修复提取时包含了```python中最后一个n和换行符的问题
    code = message[code_start + 9:code_end].strip()
    return code

def process_example(example, lang, code_output):
    # 提取生成的代码
    # 合并原始prompt和生成的代码
    example['output'] = code_output
    return {
        'task_id': example['task_id'],
        'completion': example['prompt'] + '\n' + code_output
    }

def display_evaluation_info(example, code_output, result=None):
    # 显示任务要求
    console.print(Panel(example['prompt'], title="[bold blue]Task Requirement", border_style="blue"))
    
    # 显示生成的代码（带语法高亮）
    syntax = Syntax(code_output, "python", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="[bold green]Generated Code", border_style="green"))
    
    # 如果有评测结果，显示评测结果
    if result:
        console.print(Panel(str(result), title="[bold yellow]Evaluation Result", border_style="yellow"))

async def generate_main(args):
    
    lang = args.language
    saved_path = args.output_path
    # 确保output目录存在
    os.makedirs(os.path.dirname(saved_path), exist_ok=True)
    problem_file = str(data_abs_dir / f"humaneval-{lang}.jsonl") # 需要加一个str才行

    examples = [json.loads(x) for x in open(problem_file) if x.strip()]
    
    team = Team()
    team.hire([Coder(), Tester(), Reviewer()])
    team.invest(investment=3.0)

    # 初始化已生成的示例列表
    generated_examples = []
    last_task_id = None

    # 尝试加载已有的生成结果
    try:
        with open(saved_path, 'r') as fr:
            for line in fr:
                generated_examples.append(json.loads(line))
            if generated_examples:
                last_task_id = int(generated_examples[-1]['task_id'].split('/')[1])
                print(f"Resuming from task_id: {last_task_id}")
    except FileNotFoundError:
        pass

    for i, ex in enumerate(tqdm(examples)):
        task_id = int(ex['task_id'].split('/')[1])
        
        # 跳过已处理的示例
        if last_task_id and task_id <= last_task_id:
            continue

        try:
            # 运行MetaGPT多轮协作流程
            team.run_project(ex['prompt'])
            messages = await team.run(n_round=3)
            # 获取Coder生成的代码
            code_output = extract_code_from_message(message=messages)
            print(code_output)
            
            print("\nCode extracted successfully\n")
            # 显示当前示例的代码和评测结果
            display_evaluation_info(ex, code_output)
            
            # 处理示例
            processed_ex = process_example(ex, lang, code_output)
            generated_examples.append(processed_ex)

            # 每处理5个示例保存一次
            if (i + 1) % 5 == 0:
                with open(saved_path, 'a') as fw:
                    for example in generated_examples[-5:]:
                        fw.write(json.dumps(example) + '\n')
                    print(f"Saved {5} processed examples to {saved_path}")

        except Exception as e:
            print(f"Error processing example {ex['task_id']}: {e}")

    # 最终保存所有结果
    with open(saved_path, 'w') as fw:
        for ex in generated_examples:
            fw.write(json.dumps(ex) + '\n')

    return saved_path

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output_path', type=str, default='output/meta_python.jsonl')
    parser.add_argument('--language', type=str, default='python')
    parser.add_argument('--temp_dir', type=str, default='tmp')
    args = parser.parse_args()
    
    import asyncio
    output_file = asyncio.run(generate_main(args))
    
    # 保持原有评估逻辑
    result = evaluate_functional_correctness(
        input_file=output_file,
        tmp_dir=args.temp_dir,
        n_workers=8,
        timeout=3.0,
        problem_file=data_abs_dir / f"humaneval-{args.language}.jsonl",
        language=args.language
    )
    print("\nFinal Evaluation Result:")
    console.print(Panel(str(result), title="[bold yellow]Final Evaluation Result", border_style="yellow"))
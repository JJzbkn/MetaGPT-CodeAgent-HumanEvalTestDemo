# MetaGPT-CodeAgent-HumanEvalTest

## 项目简介

本项目是一个基于MetaGPT框架的代码智能体评测系统，主要用于在HumanEval数据集上评估代码生成能力。项目采用多智能体协作的方式，通过Coder、Tester和Reviewer三个角色的配合，实现了更完整的代码生成和评估流程。

## 主要特点

- **多智能体协作**：
  - Coder：负责代码生成，采用Chain-of-Thought方法分解问题并生成代码
  - Tester：创建全面的测试用例，关注边界条件和性能测试
  - Reviewer：审查代码和测试，提供改进建议

- **评测功能**：
  - 支持多种编程语言的评测（Python、Java、JavaScript等）
  - 使用HumanEval数据集进行标准化评估
  - 提供详细的评测结果展示

- **代码生成改进**：
  - 采用Chain-of-Thought方法提升代码质量
  - 自动生成测试用例确保代码可靠性
  - 代码审查环节把控代码质量

## 安装说明

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/MetaGPT-CodeAgent-HumanEvalTest.git
cd MetaGPT-CodeAgent-HumanEvalTest
```

2. 安装依赖：
    详见MetaGPT官方文档

## 使用方法

### 运行评测

```bash
python metagpt_eval.py --language python --output_path output/meta_python.jsonl
```

参数说明：
- `--language`：指定评测的编程语言
- `--output_path`：指定输出结果的保存路径
- `--temp_dir`：指定临时文件目录（默认为tmp）

### 查看结果

程序会实时显示：
- 任务要求
- 生成的代码（带语法高亮）
- 评测结果

最终会输出整体评测结果，包含pass@k等指标。

## 项目结构

```
├── HumanEval/
│   ├── data/              # HumanEval数据集
│   ├── human_eval/        # 评测核心代码
│   ├── metagpt_eval.py    # MetaGPT评测主程序
│   └── utils/             # 工具函数
```

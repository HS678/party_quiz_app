# 入党积极分子在线刷题

这是一个基于 Streamlit 的本地刷题网页应用，题库由项目内的 JSON 数据文件提供，适合在 Windows 电脑上离线练习和模拟考试。

## 项目基本情况

- 技术栈：Python + Streamlit。
- 入口文件：`app.py`。
- 题库文件：`data/questions.json`。
- 本机练习进度：`data/progress.json`。
- 本机错题本：`data/wrong_book.json`。
- 当前题库规模：单选题 306 道，多选题 78 道，共 384 道。

主要功能：

- 随机单选题练习。
- 随机多选题练习。
- 顺序刷题，先单选后多选。
- 模拟考试，单选 70 道 + 多选 30 道，满分 100 分。
- 错题本，支持错题练习和错题记录查看。
- 一题一页展示，右侧提供题号索引。
- 自动保存本机进度，关闭网页后再次打开可继续上次练习。

## 项目结构

```text
party_quiz_app/
├─ app.py                    # Streamlit 应用入口
├─ requirements.txt          # Python 依赖
├─ start_quiz.bat            # Windows 启动脚本
├─ stop_quiz.bat             # Windows 停止脚本
├─ run_quiz_hidden.vbs       # 后台隐藏启动脚本
├─ data/
│  ├─ questions.json         # 题库
│  ├─ progress.json          # 本机进度
│  └─ wrong_book.json        # 本机错题本
├─ scripts/                  # 题库构建、解析增强脚本
├─ source/                   # 原始题库资料
└─ tests/                    # 自动化测试
```

## 普通启动方式

先进入项目目录：

```powershell
cd D:\AAWorkspace\party_quiz_app
```

创建并激活 Python 环境。已使用 Anaconda 的电脑可以执行：

```powershell
conda create -n FL1 python=3.11 -y
conda activate FL1
```

安装依赖：

```powershell
pip install -r requirements.txt
```

启动应用：

```powershell
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

启动后在浏览器打开：

```text
http://127.0.0.1:8501
```

注意：不要使用 `python app.py` 启动。本项目是 Streamlit 应用，需要通过 `streamlit run app.py` 运行。

## Windows 本机部署方式

项目已经提供了 Windows 启停脚本，适合放在本机固定目录后长期使用。

### 1. 放置项目

推荐将项目放在：

```text
D:\AAWorkspace\party_quiz_app
```

如果放在其他目录，需要同步修改以下脚本中的项目路径：

- `start_quiz.bat`
- `run_quiz_hidden.vbs`

### 2. 准备 Python 环境

当前 `start_quiz.bat` 默认使用：

```bat
call D:\Anaconda\condabin\conda.bat activate FL1
```

如果你的 Anaconda 安装路径或环境名不同，请修改这一行。例如：

```bat
call C:\Users\你的用户名\anaconda3\condabin\conda.bat activate FL1
```

然后在该环境中安装依赖：

```powershell
cd D:\AAWorkspace\party_quiz_app
conda activate FL1
pip install -r requirements.txt
```

### 3. 使用脚本启动

双击运行：

```text
start_quiz.bat
```

脚本会在本机 `127.0.0.1:8501` 启动服务。浏览器访问：

```text
http://127.0.0.1:8501
```

### 4. 后台隐藏启动

如果不想显示命令行窗口，可以双击：

```text
run_quiz_hidden.vbs
```

也可以把 `run_quiz_hidden.vbs` 或它的快捷方式放到桌面，之后双击快捷方式启动。

### 5. 开机自启

如果希望电脑开机后自动在后台启动刷题服务，可以把 `run_quiz_hidden.vbs` 的快捷方式放入 Windows 启动文件夹。

操作步骤：

1. 右键 `run_quiz_hidden.vbs`，选择“创建快捷方式”。
2. 按 `Win + R` 打开“运行”窗口。
3. 输入以下命令并回车：

```text
shell:startup
```

4. 将刚创建的 `run_quiz_hidden.vbs` 快捷方式复制到打开的启动文件夹中。
5. 下次登录 Windows 后，系统会自动运行该快捷方式，并在后台启动本项目。

开机自启后，浏览器访问：

```text
http://127.0.0.1:8501
```

如果不再需要开机自启，只需要从启动文件夹中删除这个快捷方式。

### 6. 停止服务

双击运行：

```text
stop_quiz.bat
```

该脚本会结束监听 `8501` 端口的 Streamlit 进程。

## 保留本机数据

以下两个文件保存的是个人本机数据：

```text
data/progress.json
data/wrong_book.json
```

升级或替换项目时，如果想保留练习进度和错题本，请先备份这两个文件；更新完成后再复制回新项目的 `data/` 目录。

## 测试

运行自动化测试：

```powershell
pytest
```

如果本机已安装 Streamlit，测试会包含 Streamlit UI 相关用例。

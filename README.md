# 猜词游戏

基于 BGE 模型的 Web 猜词游戏。系统从随机词库中选择目标词，用户输入猜测词，系统使用 BGE 模型返回语义相似度百分比。

## 安装 & 运行

```bash
cd backend
pip install -r requirements.txt
python app.py
```

打开浏览器访问 `http://localhost:5000`

## 项目结构

```
├── backend/
│   ├── app.py          # Flask API
│   ├── similarity.py   # BGE 语义相似度计算
│   ├── word_bank.py    # 词库管理
│   ├── game_manager.py # 游戏状态管理
│   ├── config.py       # 配置文件
│   ├── words.json      # 词库
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
└── README.md
```

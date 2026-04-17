# Yartix 主文件

本文件為快速入口，完整說明請看 README.md。

## 快速開始

1. 安裝依賴

```bash
pip install -r requirements.txt
```

2. 建立環境變數

```bash
copy .env.example .env
```

3. 啟動服務

```bash
python run.py
```

4. 部署啟動命令

```bash
gunicorn backend.app:app
```

## 手機閱讀建議

- 建議用直式閱讀此文件。
- 每段指令可直接複製執行。
- 若畫面太窄，先執行第 1 到第 3 步即可完成本機啟動。

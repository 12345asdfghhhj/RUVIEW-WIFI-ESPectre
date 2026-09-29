# RuView Sense Web MVP

一个可在 Windows 电脑运行、手机通过同一局域网浏览器访问的 RuView 可视化原型。仅使用 Python 标准库，不需要 pip 安装依赖。

## 功能
- UDP 监听（默认 `0.0.0.0:5005`）
- 解析已知的 60 字节 Feature State（magic `0xC5110006`）
- Web 仪表盘：数据接收状态、运动量、存在分数、呼吸/心率等字段
- JSON API：`GET /api/state`、`GET /api/health`
- JSONL 原始包录制：开始/停止按钮，文件存放在 `recordings/`
- 手机适配式页面

## 启动（Windows）
1. 解压本目录。
2. 在文件夹地址栏输入 `powershell`，回车打开终端。
3. 执行：

   ```powershell
   python server.py
   ```

4. 电脑浏览器打开 `http://127.0.0.1:8080`。
5. 手机连接同一个 Wi-Fi，浏览器访问电脑局域网 IP，例如 `http://192.168.31.71:8080`。实际 IP 以电脑 `ipconfig` 显示为准。
6. ESP32 固件应向电脑的 UDP 5005 发送数据。若端口被占用，可使用 `python server.py --udp-port 5006`，并同步修改设备端目标端口。

## Windows 防火墙
首次运行时，如果 Windows 弹出防火墙提示，只允许在可信的“专用网络”中访问。必要时在防火墙中允许 Python 接收专用网络流量。不要把服务端口映射到公网。

## 重要：协议与算法边界
- Feature State 的字段偏移依据当前项目提供的协议线索实现，必须与当前固件的 `rv_feature_state.h` 核对。若字段顺序或包长不同，需要修改 `parse_feature()`。
- 界面中的虚拟人体是示意图，不是实时人体成像或定位结果。
- 本版本不实现跌倒识别、身份识别、真实人体骨架重建或可靠医疗监测。
- 呼吸率/心率字段仅显示设备上报值；在未完成校准与独立验证前，不应作为医疗或紧急救援依据。

## 常用命令

```powershell
python server.py --port 8080 --udp-port 5005
```

## 项目结构

```text
ruview_web_mvp/
├── server.py          # UDP采集、Feature State解析、HTTP API、录制
├── static/index.html  # 自适应Web界面
├── plugins/           # 后续插件扩展说明
└── recordings/        # 运行时自动生成
```

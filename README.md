# Skills – 智能体技能集合

A collection of intelligent-agent skills implemented in Python.

---

## 技能 1 – 局域网设备扫描 & 网络唤醒 (LAN Scanner & Wake-on-LAN)

### 功能说明

| 功能 | 说明 |
|------|------|
| `scan_lan()` | 扫描局域网，发现所有活跃设备，返回 IP / MAC / 主机名 |
| `wake_on_lan()` | 发送 WOL 魔法包，远程唤醒目标设备 |

### 安装

```bash
pip install -e .
# 若需完整 ARP 扫描（更准确）请安装 scapy：
pip install scapy
```

#### 安装 OpenClaw（nmap）以获取主机名 🦾

> **OpenClaw = [nmap](https://nmap.org)**，一款强大的开源网络扫描工具。
> 安装后，`scan_lan()` 将自动使用 nmap 作为首选引擎，
> 并通过 DNS、mDNS/Bonjour 和 NetBIOS 等多种途径解析主机名，
> 极大提升主机名的识别率。

**Linux（Debian / Ubuntu）**

```bash
sudo apt-get install nmap
pip install "skills[nmap]"   # 安装 python-nmap 绑定库
```

**macOS（Homebrew）**

```bash
brew install nmap
pip install "skills[nmap]"
```

**Windows**

1. 从 <https://nmap.org/download.html> 下载并安装 nmap。
2. 安装 Python 绑定：

```bash
pip install "skills[nmap]"
```

安装完成后运行 `nmap --version` 确认 nmap 可正常访问，随后重新运行
`scan_lan()` 即可看到完整的主机名信息。

### 在 Claude Code 中安装 (MCP 集成)

本项目内置 MCP（Model Context Protocol）服务器，可将技能直接注册到
[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 中，作为可调用工具使用。

#### 步骤一：安装软件包

```bash
pip install -e .
```

#### 步骤二：将 MCP 服务器注册到 Claude Code

```bash
claude mcp add skills -- skills-mcp
```

> **提示**：`skills-mcp` 是安装后自动注册的命令行入口，直接启动 stdio MCP 服务器。
> 你也可以用完整 Python 路径代替：
> ```bash
> claude mcp add skills -- python -m skills mcp
> ```

#### 步骤三：验证注册结果

```bash
claude mcp list
```

输出中应该可以看到 `skills` 服务器已注册。

#### 在 Claude Code 中使用

注册后，在 Claude Code 对话中直接描述需求即可：

```
帮我扫描局域网，找出所有活跃设备
```

```
帮我唤醒 MAC 地址为 aa:bb:cc:dd:ee:ff 的电脑
```

Claude 将自动调用 `scan_lan` 或 `wake_on_lan` 工具完成操作。

---

### 快速上手

#### 扫描局域网设备

```python
from skills.network import scan_lan

for device in scan_lan():          # 自动检测本机 /24 子网
    print(device)
# IP: 192.168.1.1  MAC: aa:bb:cc:dd:ee:ff  Hostname: router.local
# IP: 192.168.1.5  MAC: 11:22:33:44:55:66
```

指定子网扫描：

```python
devices = scan_lan(subnet="192.168.0.0/24", timeout=3.0)
```

#### 发送网络唤醒包（Wake-on-LAN）

```python
from skills.network import wake_on_lan

result = wake_on_lan("aa:bb:cc:dd:ee:ff", broadcast="192.168.1.255")
if result["success"]:
    print("魔法包已发送 →", result["mac"])
else:
    print("发送失败:", result["error"])
```

#### 命令行

```bash
# 扫描局域网
python -m skills scan
python -m skills scan --subnet 10.0.0.0/24 --timeout 3

# 发送唤醒包
python -m skills wake aa:bb:cc:dd:ee:ff
python -m skills wake aa:bb:cc:dd:ee:ff --broadcast 192.168.1.255 --port 9

# 启动 MCP 服务器（供 Claude Code / MCP 客户端使用）
python -m skills mcp
# 或
skills-mcp
```

### 实现原理

#### 局域网扫描

扫描引擎按以下优先级自动选择：

1. **nmap 扫描（最推荐，需安装 nmap 二进制）** – 主机发现综合使用 ARP/ICMP
   探测，并通过反向 DNS、mDNS/Bonjour、NetBIOS 等多种途径解析主机名，
   是识别主机名最可靠的方式。安装方式见 [安装 OpenClaw（nmap）](#安装-openclaw-nmap-以获取主机名-) 一节。
2. **Scapy ARP sweep（需 root）** – 发送 ARP 广播，分析应答包，准确获取 IP + MAC。
3. **Ping sweep + ARP cache（无需 root）** – 并发 ping 所有主机填充系统 ARP 缓存，再读取
   `/proc/net/arp`（Linux）或 `arp -a`（跨平台）获取 MAC 地址。

#### Wake-on-LAN 魔法包格式

```
[0xFF × 6] + [目标 MAC × 16]   = 102 字节 UDP 广播包（端口 9）
```

目标机器需在 BIOS/固件中开启 WOL 功能。

### 项目结构

```
skills/
├── skills/
│   ├── __init__.py
│   ├── __main__.py          # CLI 入口
│   ├── mcp_server.py        # MCP 服务器（Claude Code 集成）
│   └── network/
│       ├── __init__.py
│       ├── scanner.py       # 局域网设备扫描
│       └── wol.py           # Wake-on-LAN
├── tests/
│   ├── test_mcp_server.py
│   ├── test_scanner.py
│   └── test_wol.py
├── examples/
│   └── network_example.py
├── pyproject.toml
└── requirements.txt
```

### 运行测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

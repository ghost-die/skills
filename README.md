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
```

### 实现原理

#### 局域网扫描

1. **Scapy ARP sweep（推荐，需 root）** – 发送 ARP 广播，分析应答包，准确获取 IP + MAC。
2. **Ping sweep + ARP cache（无需 root）** – 并发 ping 所有主机填充系统 ARP 缓存，再读取
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
│   └── network/
│       ├── __init__.py
│       ├── scanner.py       # 局域网设备扫描
│       └── wol.py           # Wake-on-LAN
├── tests/
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

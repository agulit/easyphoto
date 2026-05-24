# 易图

便携看图软件，支持常见图片与多厂商 RAW（尼康 NEF、索尼 ARW、佳能 CR2、大疆 DNG 等）。

作者：**llso** · 联系：58539199@qq.com

## 下载

在仓库 **Releases** 页面下载 **`易图.exe`**（单文件，拷贝即用，约 66MB）。

## 启动与缓存（v1.6）

- **仍是单个 exe**，无需安装。
- **第一次运行**（或升级新版本后）：解压到  
  `%LOCALAPPDATA%\llso\yitu\<版本号>\`（约需数秒）。
- **之后每次打开**（含重启电脑）：直接运行缓存，**不再重复解压**，启动明显更快。
- 若删除上述文件夹，或安装新版本，会再次解压一次。

## 功能

- 缩放：`+` / `-` / 滚轮；切换图片自动适应窗口
- 翻页：方向键或底部缩略图条（当前项蓝色底衬高亮）
- 专业调色：亮度 / 对比度 / 高光 / 阴影 / 饱和度 / 色温 / 色相
- 全屏浏览（F11，Esc 退出）
- 旋转、裁剪、打印、复制、另存为、删除、打开所在文件夹
- 图片信息 / EXIF / GPS（含 RAW）
- 帮助 → 添加到右键菜单（资源管理器「用易图打开」）
- 深色界面，单文件便携 exe

## 从源码运行

```powershell
cd m:\seephoto
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m seephoto
```

## 打包

```powershell
.\build.ps1
```

生成 `dist\易图.exe`（内嵌应用包；用户首次运行解压到 AppData）。

## 快捷键

| 操作 | 按键 |
|------|------|
| 放大 / 缩小 | `+` `-` / 滚轮 |
| 上一张 / 下一张 | `←` `→` `↑` `↓` |
| 适应窗口 / 原尺寸 | `0` / `1` |
| 全屏 | `F11` |
| 图片信息 | `Ctrl+I` |
| 关于 | 菜单 **帮助 → 关于 易图** |

## 依赖说明

- [PySide6](https://doc.qt.io/qtforpython/) — 界面
- [Pillow](https://python-pillow.org/) — 常见格式
- [rawpy](https://github.com/letmaik/rawpy) / [LibRaw](https://www.libraw.org/) — RAW 解码

## 许可证

本项目源码采用 MIT 许可证。再分发打包版时请遵守上述第三方库各自的许可条款。

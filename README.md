# Pixel Color Stabilizer · 区域时段稳色

[English](README.en.md)

给像素动画的**指定区域、指定帧段**做逐坐标众数稳色。独立桌面工具与 Python 库，从 Pixel Studio 的区域稳色模块提取；不需要 Aseprite、Blender、GPU、AI 权重、联网服务或原来的工作台。

## 使用

Windows 普通用户：解压便携包，运行 `PixelColorStabilizer/PixelColorStabilizer.exe`。无需安装 Python 或 Aseprite。请保留整个文件夹（包含 `_internal`），不要只复制 exe。

源码用户安装 Python 3.10+（含 Tk），在此目录运行：

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install .
python -m pixel_color_stabilizer --gui
```

Windows 也可在安装后双击 `Start.cmd`。Linux 可能需要通过系统包管理器安装 `python3-tk`。源码以跨平台方式编写；本次本机验证平台为 Windows，其他平台由仓库 CI 测试核心与导入导出。

1. 打开 GIF/APNG、PNG 序列或 PNG 文件夹；精灵图请使用“精灵图”，输入单帧宽高和有效帧数，按从左到右、从上到下切分。
2. 在左侧当前素材上拖动框选，填写起止帧。坐标从 **0** 开始，帧号从 **1** 开始，首尾都包含。PNG 序列自然排序，例如 `frame2` 在 `frame10` 前。
3. 选择模式，点击“生成预览”，播放检查左右对比。缩放后可以滚动查看大画布。
4. 点击“应用当前选区”，然后继续处理下一处；可逐次撤回。预览本身不修改已应用素材，修改参数会取消旧预览。
5. 完成后点击“导出”，选择父目录和一个**尚不存在**的文件夹名。保留源文件，输出不会覆盖原素材或旧导出。

导出的文件夹可通过“文件夹”重新打开，保留时序与操作记录；重新打开后的撤回栈从空开始。关闭前请导出，程序不会自动保存会话。没有直接读取或写入 `.aseprite` 的功能；任何编辑器导出通用图片后都能接入。

## 稳色规则

每个坐标单独统计所选帧段，并不是把整个矩形涂成一种颜色。

| 模式 | 规则 |
| --- | --- |
| 只稳颜色 `preserve` | 仅统计不透明帧的 RGB 众数，保留各帧 alpha 与透明像素的隐藏 RGB；颜色平票取最早出现的颜色。 |
| 含透明投票 `majority` | 先统计空/非空帧数：透明**严格超过半数**则整段清空；否则将整段补齐为不透明 RGB 众数。空/非空平票时补齐，颜色平票仍取最早出现值。会改变轮廓。GUI 默认此模式，Python/CLI 未指定时默认 `preserve`。 |
| 可选孤立点清理 | 仅合并原始八邻域没有同色邻居的像素，保留 alpha、已有两像素及以上色簇；可显式允许清理选区外 1px。延续原模块的邻居票数、连通色簇大小、Lab 距离平票规则。 |

这是固定坐标稳色，适合静止部位和短时间段。不会跟踪物体或识别语义；移动轮廓经过选区时可能被压平，请分短段预览。

只接受 alpha 为 0/255 的像素素材；半透明、抗锯齿输入会明确报错，不会偷偷二值化。所有输入帧须画布一致。逐帧时长支持 1–65535ms；PNG 序列默认 100ms，可在打开前修改。GIF/APNG 读取已有时长，PNG 文件夹中存在本工具 `animation.json` 时按清单恢复时长。GIF 解码已丢失的信息无法恢复。

## 导出文件

| 文件 | 用途 |
| --- | --- |
| `frames/frame_000001.png` 等 | 原始尺寸 RGBA PNG 逐帧图，主要编辑与交换格式。 |
| `animation.png` | 无损 APNG 动画；保留重复帧、全部帧数、透明像素隐藏 RGB 与逐帧毫秒时长，无调色板量化。 |
| `animation.json` | 帧文件、时长、画布与已应用操作报告；配合 `frames/` 重新打开。 |
| `spritesheet.png` | RGBA 精灵图，默认每行最多 8 帧。 |
| `spritesheet.json` | 常见 Aseprite 风格的 JSON array 帧坐标和时长；也可供其他编辑器/引擎使用。末行空格不是有效帧。 |

动画导出采用 APNG，以避免 GIF 的色数与时间量化。部分图片查看器只显示 PNG 第一帧，可用支持 APNG 的浏览器播放；帧序列和 JSON 是明确的交换数据。精灵图的 JSON 不是原生 Aseprite 文件。

## 命令行和库

保存一个 `params.json`（示例坐标需替换为自己的选区）：

```json
{
  "start": 1,
  "end": 8,
  "rectangles": [{"x": 4, "y": 6, "width": 12, "height": 16}],
  "alpha_mode": "preserve",
  "cleanup_isolated": false,
  "cleanup_halo": 0
}
```

```sh
python -m pixel_color_stabilizer --input ./input_frames --params params.json --output ./result
python -m pixel_color_stabilizer --input sheet.png --cell 64 64 --frames 12 --duration 100 --params params.json --output ./result_sheet
```

API 支持 1–64 个矩形的并集，重叠不重复计数；只改指定区域与时段。`preserve` 另支持 `min_ratio`（0–1，不透明帧中的众数占比门槛），`majority` 要求该值为 0。API 返回新的数组与报告，不修改输入。

```python
from pixel_color_stabilizer import temporal_mode
from pixel_color_stabilizer.media import load_animation, Animation, export_bundle

source = load_animation("input_frames", duration=100)
frames, report = temporal_mode(source.frames, 1, 8,
    [{"x": 4, "y": 6, "width": 12, "height": 16}], alpha_mode="preserve")
export_bundle("result", Animation(frames, source.durations, [report]))
```

## 开发、测试和 Windows 打包

```sh
python -m pip install '.[build]'
python -m unittest discover -s tests -v
python -m build
```

Windows PowerShell 在已激活的干净虚拟环境中运行：

```powershell
./scripts/build_windows.ps1
```

生成 `dist/PixelColorStabilizer-windows-x64.zip`。这是整个目录的便携包，不依赖开发机路径。`.github/workflow-templates/` 提供跨平台测试和 Windows 构建的 GitHub Actions 模板。首次上传所用令牌缺少 `workflow` 权限，因此模板尚未启用；仓库维护者可通过 GitHub 网页将它们放到 `.github/workflows/` 后启用。Windows 模板支持手动触发或推送 `v*` 标签触发，产物作为 Actions artifact 下载，不会自动公开发布 Release。

运行 `python scripts/package_source.py` 可生成只含可提交文件的源码 ZIP。实际本机验证范围见 [VALIDATION.md](VALIDATION.md)。

仓库：[Ainatem/Pixel-Color-Stabilizer](https://github.com/Ainatem/Pixel-Color-Stabilizer)。源码、文档与 `.github` 纳入版本管理；`.venv`、`build`、`dist`、私人动画和缓存不提交。便携包请从仓库的 Releases 下载。

## 来源与许可

本项目代码采用 [MIT License](LICENSE)。核心 `temporal_mode` 与孤立点算法提取自本地 Pixel Studio，去除了项目管理、工作台、权重及导出程序的依赖，保留统计与平票规则。仅携带算法代码和独立工具，无 Aseprite 程序、AI 模型或用户素材。

运行库为 NumPy、Pillow、SciPy、Python/Tcl/Tk；构建工具为 PyInstaller。便携包包含其运行文件与许可证，第三方组件仍遵循各自许可证；详见 [THIRD_PARTY.md](THIRD_PARTY.md)。

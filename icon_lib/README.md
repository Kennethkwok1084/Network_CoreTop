# Icon Library Usage

This repo includes Huawei enterprise networking icon sources in PPTX and VSS formats under `icon_lib/`.

## PPTX (Enterprise_Networking_Product_Icons_S_cn.pptx)
- 已解包：`icon_lib/pptx_extract/ppt/media/`（319 个 PNG）。
- 关键信息映射：`icon_lib/pptx_media_mapping.json`，把每个 `imageXXX.png` 映射到所在幻灯片与上方文字说明（便于知道图标含义）。
- 重新解包命令（可重复执行）：
  ```bash
  mkdir -p icon_lib/pptx_extract
  unzip -q icon_lib/Enterprise_Networking_Product_Icons_S_cn.pptx -d icon_lib/pptx_extract
  ls icon_lib/pptx_extract/ppt/media | head
  ```
- 查询某个 PNG 对应文案示例（Python）：
  ```bash
  python - <<'PY'
  import json
  mapping = json.load(open('icon_lib/pptx_media_mapping.json', encoding='utf-8'))
  name = 'image8.png'  # 例：调整为目标文件名
  print(mapping.get(name))
  PY
  ```

## VSS (Enterprise_Networking_Product_Icons_S&CE&WLAN(Blue).vss)
- This is a Visio stencil (Composite Document File). No built-in parser here.
- Suggested conversions (run where tools are available):
  1) LibreOffice headless: `soffice --headless --convert-to vsdx icon_lib/Enterprise_Networking_Product_Icons_S&CE&WLAN(Blue).vss --outdir icon_lib/`
  2) Then extract shapes from VSDX with a Visio/VSDX parser or export to SVG/PNG.
- If you need the icons and cannot convert locally, fall back to the PPTX PNG set above.

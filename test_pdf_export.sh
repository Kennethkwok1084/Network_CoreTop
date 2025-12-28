#!/bin/bash
# 测试 PDF 导出功能
# 需要先安装 Graphviz: sudo apt install graphviz

echo "=== 测试 PDF 导出模块 ==="
echo

# 1. 测试 DOT 文件生成
echo "1. 生成 Core 设备的 DOT 文件..."
python -m topo.exporter.pdf Core -m dot-only -o outputs/Core_topology.dot
if [ $? -eq 0 ]; then
    echo "✓ DOT 文件生成成功"
    wc -l outputs/Core_topology.dot
else
    echo "✗ DOT 文件生成失败"
    exit 1
fi
echo

# 2. 测试 DOT → PDF 转换（如果有 dot 命令）
if command -v dot &> /dev/null; then
    echo "2. 使用 Graphviz 转换 DOT → PDF..."
    python -m topo.exporter.pdf Core -m graphviz -o outputs/Core_topology_graphviz.pdf
    if [ $? -eq 0 ]; then
        echo "✓ PDF 转换成功"
        ls -lh outputs/Core_topology_graphviz.pdf
    else
        echo "✗ PDF 转换失败"
    fi
else
    echo "2. ⚠ 未安装 Graphviz (dot)，跳过 PDF 转换测试"
    echo "   安装方法: sudo apt install graphviz"
fi
echo

# 3. 测试 Mermaid 方式（如果有 mmdc 命令）
if command -v mmdc &> /dev/null; then
    echo "3. 使用 Mermaid CLI 转换 Mermaid → PDF..."
    python -m topo.exporter.pdf Core -m mermaid -o outputs/Core_topology_mermaid.pdf
    if [ $? -eq 0 ]; then
        echo "✓ Mermaid PDF 生成成功"
        ls -lh outputs/Core_topology_mermaid.pdf
    else
        echo "✗ Mermaid PDF 生成失败"
    fi
else
    echo "3. ⚠ 未安装 Mermaid CLI (mmdc)，跳过测试"
    echo "   安装方法: npm install -g @mermaid-js/mermaid-cli"
fi
echo

# 4. 测试 Problem 设备
echo "4. 生成 Problem 设备的 DOT 文件（包含 suspect 链路）..."
python -m topo.exporter.pdf Problem -m dot-only -o outputs/Problem_topology.dot
if [ $? -eq 0 ]; then
    echo "✓ Problem 设备 DOT 生成成功"
    grep -E "style=dashed|color=orange" outputs/Problem_topology.dot && \
        echo "✓ 检测到 suspect 链路样式" || \
        echo "ℹ 无 suspect 链路"
else
    echo "✗ Problem 设备 DOT 生成失败"
fi
echo

echo "=== 测试完成 ==="
echo "生成的文件："
ls -lh outputs/*.dot 2>/dev/null
ls -lh outputs/*.pdf 2>/dev/null

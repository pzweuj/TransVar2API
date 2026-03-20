#!/usr/bin/env python3
"""
修补 transvar 的 localdb.py 以修复 KeyError: 'product' 错误

问题: transvar 在解析 NCBI RefSeq GFF3 文件时，
某些条目既没有 'Name' 也没有 'product' 属性，
导致 KeyError。

修复: 将代码改为使用 .get() 方法并提供 ID 作为后备选项。
"""

import os
import sys

def find_transvar_localdb():
    """查找 transvar 的 localdb.py 文件路径"""
    import transvar
    transvar_path = os.path.dirname(transvar.__file__)
    localdb_path = os.path.join(transvar_path, 'localdb.py')
    return localdb_path

def patch_localdb(localdb_path):
    """修补 localdb.py 文件"""

    # 读取文件内容
    with open(localdb_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找需要替换的行
    # 原始代码: t.name = info['Name'] if 'Name' in info else info['product']
    # 修复后: t.name = info.get('Name') or info.get('product') or info.get('ID')

    old_line = "t.name = info['Name'] if 'Name' in info else info['product']"
    new_line = "t.name = info.get('Name') or info.get('product') or info.get('ID')"

    if old_line in content:
        content = content.replace(old_line, new_line)
        print(f"已修补: {localdb_path}")
        print(f"  原代码: {old_line}")
        print(f"  新代码: {new_line}")
    elif new_line in content:
        print(f"已修复，无需重复修补: {localdb_path}")
        return True
    else:
        print(f"警告: 未找到目标代码行，可能版本不同")
        # 尝试查找类似的代码模式
        import re
        pattern = r"t\.name\s*=\s*info\[.*?\].*?info\[.*?\]"
        matches = re.findall(pattern, content)
        if matches:
            print(f"找到可能的代码: {matches}")
        return False

    # 写回文件
    with open(localdb_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return True

def main():
    print("=" * 50)
    print("TransVar localdb.py 修补脚本")
    print("=" * 50)

    try:
        localdb_path = find_transvar_localdb()
        print(f"找到 localdb.py: {localdb_path}")
    except ImportError:
        print("错误: 未找到 transvar 模块，请先安装 transvar")
        sys.exit(1)

    if not os.path.exists(localdb_path):
        print(f"错误: localdb.py 不存在于 {localdb_path}")
        sys.exit(1)

    success = patch_localdb(localdb_path)

    if success:
        print("\n修补成功!")
    else:
        print("\n修补失败，请手动检查")
        sys.exit(1)

if __name__ == '__main__':
    main()
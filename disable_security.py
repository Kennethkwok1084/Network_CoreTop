#!/usr/bin/env python3
"""
禁用所有安全检查的补丁脚本
用于开发/测试环境
"""
import re

def patch_file(filepath, replacements):
    """应用文本替换补丁"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old_pattern, new_text in replacements:
        content = re.sub(old_pattern, new_text, content, flags=re.DOTALL)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 已修改: {filepath}")

# 1. app_v2.py - 移除 SECRET_KEY 强制检查
patch_file('topo/web/app_v2.py', [
    # SECRET_KEY 检查
    (r'secret_key = os\.environ\.get\(\'SECRET_KEY\'\)\s+if not secret_key:.*?"\s*\)',
     "secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-for-testing-only')"),
    
    # Cookie 安全配置
    (r"app\.config\['SESSION_COOKIE_SECURE'\] = True",
     "app.config['SESSION_COOKIE_SECURE'] = False  # 开发模式"),
    
    # CSRF 保护
    (r'def csrf_protect\(f\):.*?if request\.method == \'POST\':.*?return redirect\(.*?\)\s+return f\(\*args, \*\*kwargs\)',
     '''def csrf_protect(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 开发模式：跳过 CSRF 验证
            return f(*args, **kwargs)
        return decorated_function'''),
])

# 2. management_schema.py - 移除密码强度检查
patch_file('topo/db/management_schema.py', [
    # 移除密码必需检查
    (r'password = password or os\.environ\.get\(\'ADMIN_PASSWORD\'\)\s+if not password:.*?"\s*\)',
     "password = password or os.environ.get('ADMIN_PASSWORD', 'admin123')"),
    
    # 移除密码强度检查
    (r'if len\(password\) < 12:.*?"\s*\)',
     "# 开发模式：跳过密码强度验证"),
])

print("\n" + "="*60)
print("✅ 所有安全检查已禁用")
print("="*60)
print("\n现在可以直接启动，无需任何环境变量：")
print("  bash start_web_management.sh")
print("\n默认登录凭证：")
print("  用户名: admin")
print("  密码: admin123")
print("\n⚠️  警告：仅用于开发/测试环境！")
print("="*60)

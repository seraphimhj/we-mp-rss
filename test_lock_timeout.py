"""check_lock 陈旧锁超时的自检:python3 test_lock_timeout.py

二维码文件超过 timeout 秒必须视为过期锁并删除放行,
否则授权过期后的重试和通知会被永久拦截。
不依赖第三方包(重依赖全部 stub 掉)。
"""
import importlib.util
import os
import sys
import tempfile
import time
import types

# stub 掉 wx_api.py 的重依赖,只为拿到 WeChatAPI.check_lock
def _stub(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m

_stub('sqlalchemy', true=True)
_stub('attr', s=None)
_stub('psutil')


class _Session:  # 模块 import 时会实例化 WeChatAPI,需要能创建 Session
    def __init__(self):
        self.headers = {}


_stub('requests', Session=_Session)
pil = _stub('PIL', Image=None)
_stub('PIL.Image')
pil.Image = sys.modules['PIL.Image']
_noop = lambda *a, **k: None
_stub('core.print', print_warning=_noop, print_success=_noop, print_error=_noop)
_stub('core', )
_stub('driver', __path__=[])
_stub('driver.token', get=_noop, set_token=_noop)

_here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('driver.wx_api', os.path.join(_here, 'driver', 'wx_api.py'))
wx_api = importlib.util.module_from_spec(spec)
sys.modules['driver.wx_api'] = wx_api
spec.loader.exec_module(wx_api)

api = object.__new__(wx_api.WeChatAPI)  # 跳过 __init__

with tempfile.TemporaryDirectory() as d:
    qr = os.path.join(d, 'wx_qrcode.png')
    api.wx_login_url = qr

    # 无文件 → 无锁
    assert api.check_lock() is False

    # 新文件 → 有锁
    open(qr, 'w').close()
    assert api.check_lock() is True
    assert os.path.exists(qr)

    # 超时的旧文件 → 视为陈旧锁,删除并放行
    old = time.time() - 301
    os.utime(qr, (old, old))
    assert api.check_lock() is False
    assert not os.path.exists(qr), '陈旧二维码文件应被删除'

    # 自定义 timeout 生效
    open(qr, 'w').close()
    old = time.time() - 10
    os.utime(qr, (old, old))
    assert api.check_lock(timeout=5) is False

print('test_lock_timeout: OK')

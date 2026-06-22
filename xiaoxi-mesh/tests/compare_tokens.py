#!/usr/bin/env python3
"""精确比较本地和远程生成的token是否一致"""
import asyncio, sys, os, jwt, base64

async def main():
    proj = os.path.dirname(os.path.dirname(__file__))
    cfg_path = os.path.join(proj, "config.yaml")
    sys.path.insert(0, proj)
    
    import yaml
    from auth import Auth
    
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    
    key = cfg["auth"]["secret_key"]
    print(f"Config路径: {cfg_path}")
    print(f"密钥: {key}")
    
    a = Auth(key)
    token = a.create_token("xiaoqing", "agent")
    print(f"Token长度: {len(token)}")
    
    # 验证
    p = a.verify_token(token)
    print(f"本地验证: {'✅' if p else '❌'}")
    if p:
        print(f"  agent_id: {p.agent_id}")
        print(f"  exp: {p.exp}")
    
    # base64编码输出（用于从远程获取的token做对比）
    b64 = base64.b64encode(token.encode()).decode()
    print(f"Base64: {b64}")

if __name__ == "__main__":
    asyncio.run(main())

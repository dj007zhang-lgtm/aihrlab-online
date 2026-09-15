import re, os
files = ['mckinsey-human-ai-orchestration.html','ai-governance-gap-hr-2026.html',
         'pod-org-ai-agent-2026.html','global-talent-supply-chain-2026.html',
         'ai-hr-landing-3-high-roi-plays.html','bytedance-context-management-ai-agent.html']
for f in files:
    p = os.path.join('articles', f)
    if not os.path.exists(p):
        print('MISS', f); continue
    t = open(p, encoding='utf-8').read()
    blocks = re.findall(r'<(?:pre|code|blockquote)[^>]*>(.*?)</(?:pre|code|blockquote)>', t, re.S | re.I)
    joined = ' '.join(blocks)
    half = len(re.findall(r'[,;:!?\(\)\[\]{}]', joined))
    full = len(re.findall(r'[，；：！？（）【】｛｝]', joined))
    print(f'{f}: 代码/引用块 {len(blocks)} 个 | 块内半角 {half} 全角 {full}')
    for b in blocks[:1]:
        sample = re.sub(r'<[^>]+>', ' ', b)
        sample = re.sub(r'\s+', ' ', sample).strip()[:70]
        print('   样例:', sample)

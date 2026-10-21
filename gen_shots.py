# -*- coding: utf-8 -*-
"""生成各页签的临时预览 HTML，供无头浏览器截图（不改动源文件，用完即删）。"""
import os

ROOT = r'D:\桌面\APP'
STATIC = os.path.join(ROOT, 'static')

with open(os.path.join(STATIC, 'index.html'), encoding='utf-8') as f:
    html = f.read()


def activate(html, tab):
    html = html.replace('<button class="tab active" data-tab="search">',
                        '<button class="tab" data-tab="search">')
    html = html.replace('<button class="tab" data-tab="%s">' % tab,
                        '<button class="tab active" data-tab="%s">' % tab)
    html = html.replace('<section id="panel-search" class="panel active">',
                        '<section id="panel-search" class="panel">')
    html = html.replace('<section id="panel-%s" class="panel">' % tab,
                        '<section id="panel-%s" class="panel active">' % tab)
    return html


tabs = {'convert': '坐标轨迹', 'batch': '批量导入', 'plan': '今日计划', 'settings': '设置'}
for tab in tabs:
    with open(os.path.join(STATIC, '_shot_%s.html' % tab), 'w', encoding='utf-8') as f:
        f.write(activate(html, tab))
    print('generated _shot_%s.html' % tab)

# 搜索结果：默认页签 + 自动搜索脚本
auto_script = '''
<script>
window.addEventListener('load', function () {
  setTimeout(function () {
    document.getElementById('originInput').value = '北京市朝阳区阜通东大街';
    document.getElementById('destInput').value = '天安门';
    document.getElementById('searchBtn').click();
  }, 800);
});
</script>
</body>'''
with open(os.path.join(STATIC, '_shot_search_result.html'), 'w', encoding='utf-8') as f:
    f.write(html.replace('</body>', auto_script))
print('generated _shot_search_result.html')

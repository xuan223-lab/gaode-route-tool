# 高德路径搜索与下载工具

![version](https://img.shields.io/badge/version-v0.1.0-blue)
![license](https://img.shields.io/badge/license-MIT-green)

一个**只在本机浏览器运行**的网页小工具：输入起终点搜索高德路线，看地图、看分段导航、导出 CSV / GeoJSON（WGS84），并支持坐标互转、Excel 批量导入、里程统计、今日计划、轨迹录制与离线瓦片缓存。

> **开箱即用**：不想装 Python？直接到 [Releases](https://github.com/xuan223-lab/gaode-route-tool/releases) 下载 `GaodeRouteTool.exe`，双击即可运行。

## 功能

- 路线搜索：驾车 / 步行 / 骑行 / 公交，支持输入**地址**或**经纬度（默认 WGS84）**
- 驾车策略：最快捷 / 最短距离 / 少收费 / 躲避拥堵 / 不走高速
- 途经点：驾车支持起终点间插入多个途经点
- 地图显示（Leaflet + 高德底图瓦片）+ 总距离 / 预计耗时 + 分段导航指令表
- 实时路况：驾车路线按畅通/缓行/拥堵/严重拥堵着色
- 导出：单条路线 CSV、GeoJSON（坐标系 **WGS84**）
- 坐标互转：GCJ-02 ↔ WGS84
- 定位 + 轨迹录制：一键把当前位置填为起点；录制轨迹并导出 WGS84 的 GeoJSON / CSV
- 批量：从 Excel（列：**起点 / 终点 / 出行方式 / 备注**）导入多组起终点，一次搜索、一次下载多条路线，导出**里程统计表**
- 今日计划：当天路线任务集中管理、排序、逐条查看、一键全部导出
- 备份 / 恢复：一键把 `data/` + `downloads/` 打包为 zip，或从 zip 恢复（恢复前自动备份到 `backups/`）
- 离线地图：浏览过的地图瓦片自动缓存到 `tiles/`，断网后已缓存区域仍可显示
- 本地持久化：API Key、搜索历史、今日计划、下载文件，重启不丢失

## 运行

### 方式一：下载 exe（推荐，无需 Python）

1. 到 [Releases](https://github.com/xuan223-lab/gaode-route-tool/releases) 下载 `GaodeRouteTool.exe`；
2. 放到任意目录，双击运行；
3. 浏览器会自动打开 `http://127.0.0.1:8000`；
4. 首次使用到「设置」页粘贴高德 Key。

> 数据（`data/`、`downloads/`、`tiles/`）会生成在 **exe 同级目录**，重启不丢失。
> 关闭黑色命令行窗口即停止服务。

### 方式二：从源码运行

1. 安装 Python 3.8+（若未安装，请到 python.org 下载，安装时勾选 "Add to PATH"）。
2. 安装依赖（只需一个库）：

   ```bat
   pip install -r requirements.txt
   ```

   > 若不想装 openpyxl，批量导入也可直接用 `.csv` 文件（无需任何依赖）。

3. 双击运行（或在命令行执行）：

   ```bat
   python app.py
   ```

   浏览器会自动打开 `http://127.0.0.1:8000`（若没自动打开，手动访问该地址）。

4. 首次使用，先到「**设置**」页粘贴你的高德 **Web 服务 Key**（申请见下）。

## 打包为 exe

```bat
build_exe.bat
```

或手动执行：

```bat
pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --name GaodeRouteTool ^
  --add-data "static;static" app.py
```

产物位于 `dist\GaodeRouteTool.exe`（约 29 MB，单文件，内含前端静态资源）。

## 测试

全部测试用 Python 标准库 `unittest`，无需额外安装：

```bat
python run_tests.py
```

- 单元测试覆盖：坐标互转、接口解析（驾车/步行/骑行/公交、路况 tmcs、途经点）、本地持久化、导出（CSV/GeoJSON/里程统计/轨迹）、备份恢复、瓦片缓存、HTTP 接口。
- 其中 `tests/test_integration_amap.py` 会用已配置的 Key 做真实联调（需要联网）。

## 高德 Key 申请（免费）

1. 打开 https://lbs.amap.com/ 注册 / 登录；
2. 进入「控制台」，完成个人开发者实名认证（免费）；
3. 「应用管理 → 我的应用 → 创建新应用」；
4. 在应用下「添加 Key」，**服务平台选「Web 服务」**；
5. 复制 Key，粘贴到本工具「设置」页保存。

> ⚠️ **公交 / 地铁**：高德的「公交路径规划」接口对个人免费 Key 默认无权限（返回 `INSUFFICIENT_PRIVILEGES` / 错误码 10012）。如需要使用公交换乘，需在高德开放平台为 Key 单独开通「公交路径规划」服务权限（通常需企业认证或单独申请）。驾车 / 步行 / 骑行不受影响。

## 目录结构

```
app.py              后端主程序（标准库 http.server）
amap_client.py      高德接口封装（地理/逆地理编码、驾车/步行/骑行/公交）
coord.py            GCJ-02 ↔ WGS84 坐标互转
storage.py          本地 JSON 持久化
paths.py            路径解析（兼容源码运行与 exe 运行）
run_tests.py        测试运行器
build_exe.bat       一键打包为 exe
tests/              unittest 测试
static/             前端页面（index.html / style.css / app.js / leaflet/）
data/               本地数据（config.json、history.json、plan.json）
downloads/          导出的 CSV / GeoJSON 文件
tiles/              离线地图瓦片缓存
backups/            恢复前的自动备份
PRD.md              产品需求文档
DEVELOPMENT_PLAN.md 开发计划
```

## 说明

- 所有数据只保存在本机（`data/`、`downloads/`、`tiles/`、`backups/`），不登录、不上云。
- 仅"搜索路线"、"公交/逆地理编码"和"加载地图底图（首次）"需要联网调用高德。
- 输入经纬度按 **WGS84** 处理，App 会自动转 GCJ-02 再请求高德，导出时再转回 WGS84。
- 导出 CSV 使用 UTF-8 BOM，双击可用 Excel 正常打开中文。

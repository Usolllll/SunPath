# 院校地图参考位置

`university_locations.json` 为当前 60 所院校提供 WGS84 经纬度，独立于模拟招生数据；运行时只读本地文件，不调用地理编码服务，也不根据校名随机生成坐标。

- `precision=university`：Wikidata 的学校坐标，表示一个参考位置，不保证是当前本科主校区，也不覆盖全部校区。每条 `source_url` 可追溯对应实体。
- `precision=city`：尚未核实学校坐标，使用所在城市参考点。当前为杭州电子科技大学和温州大学，页面会明确提示“所在城市参考位置（校区坐标待核实）”。后续核实校区后可替换该条记录。
- 东华大学使用上海的 [Q837544](https://www.wikidata.org/wiki/Q837544)，不可与台湾的国立东华大学混淆。
- 浙江工商大学当前参考点位于桐庐，页面说明不是下沙校区，避免将多个校区混为同一地址。

来源：[Wikidata Query Service](https://query.wikidata.org/)，2026-11-09 查询并核对。Wikidata 结构化数据采用 [CC0](https://www.wikidata.org/wiki/Wikidata:Licensing)；底图版权与坐标来源分开标识。后续新增学校如果没有坐标，仍在列表显示，但不在地图伪造标记。

修改坐标文件后重启后端以刷新缓存。字段：`latitude`、`longitude`、`source_url`、`precision`、`label`。不要把高德/腾讯 GCJ-02 或百度 BD-09 坐标直接放入这个 WGS84 文件。

前端底图使用天地图官方 JS API 4.0；上述坐标用于 `T.LngLat(经度, 纬度)`，位置数据来源与底图服务分开标注。地图的国界、注记、审图号和版权信息由官方 SDK 展示，本坐标文件不定义行政区划或国界。

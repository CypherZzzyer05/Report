# 光学仿真报告

此仓库集中保存报告、图表与对应数据；生成器代码保存在各自独立仓库。

最新的[模型实验与保留权重](https://github.com/CypherZzzyer05/Optics_design/tree/1b31513/Metaformer_As2Se3)已单独归档，报告区分训练、验证、测试曲线与已有FDTD光谱。

| 日期 | 报告 | 内容 |
| --- | --- | --- |
| 2026-10-27 | [MetaformerPro：共振局部细分输入编码](reports/2026-10-27_metaformerpro_resonance/README.md) · [离线 HTML](reports/2026-10-27_metaformerpro_resonance/index.html) | 六次新训练；同参数量均匀加密与共振取样对照；共振验证改善0.41%，未优于均匀加密，继续保留原模型；实验权重另存 |
| 2026-10-27 | [光谱信息、特征表达与真实加工间隙](reports/2026-10-27_information_and_fabrication/README.md) · [离线 HTML](reports/2026-10-27_information_and_fabrication/index.html) | 文献调研与1000条旋转/周期几何核对；最小开口4.615 nm，190条低于50 nm；区分可辨识性与特征编码，未新增训练或FDTD |
| 2026-10-27 | [MetaformerPro：4／8／12层编码器对照](reports/2026-10-27_metaformerpro_depth/README.md) · [离线 HTML](reports/2026-10-27_metaformerpro_depth/index.html) | 六次新训练；12层验证误差降2.8%，测试误差升6.3%；深度实验权重与全部曲线保留，现用4层权重不覆盖 |
| 2026-10-27 | [MetaformerPro：新层序数据上的进一步优化](reports/2026-10-27_metaformerpro_refine/README.md) · [离线 HTML](reports/2026-10-27_metaformerpro_refine/index.html) | 三方案各3种子、共九次新训练；127万/215万参数均未改善验证；保留32万参数原圆周头；dY与角度信号诊断 |
| 2026-10-24 | [MetaformerPro：新层序1000样本训练与验证](reports/2026-10-24_metaformerpro_topmetal1000/README.md) · [离线 HTML](reports/2026-10-24_metaformerpro_topmetal1000/index.html) | 23日训练、24日汇总；厚SiO₂／Au100／As₂Se₃；两种输出头各3种子；固定800/100/100；长波双谷覆盖与候选结构示意 |
| 2026-10-22 | [角度镜像同谱、金层与网格核对](reports/2026-10-22_rotation_jc220/README.md) | 12组完整器件与2组平膜；角度镜像等价；金层影响明显；带金局部网格未收敛，暂缓大批量生产；服务器单样本参考包 |
| 2026-10-22 | [数据生成器 2.2.0：Au 损耗修正与运行验证](reports/2026-10-22_generator220_release/README.md) | 新 Au 模型通过全部固定材料门槛；平膜 8/4 nm 解析核对；一个完整四聚体真实求解成功；106 项程序测试；服务器更新说明 |
| 2026-10-21 | [Au 损耗修正候选与平面金膜网格核对](reports/2026-10-21_gold_film_validation/README.md) | 9组原生薄膜对照；恢复损耗的候选尚未通过全部材料门槛；CV1改善平膜8/4 nm微弱透射一致性，完整四聚体仍待验证 |
| 2026-10-21 | [逆向 Metaformer：1000样本训练与回仿真](reports/2026-10-21_inverse_roundtrip_207/README.md) · [离线 HTML](reports/2026-10-21_inverse_roundtrip_207/index.html) | 800/100/100训练与测试；样本207双谷保留、第二谷偏移4 nm；确认服务器数据也存在Au损耗拟合缺失 |
| 2026-10-18 | [器件可行性与可加工性调研](reports/2026-10-18_device_feasibility/README.md) · [PDF](output/pdf/device_feasibility_2026-10-18.pdf) | 16 项文献/官方来源；Au 损耗拟合重大更正；1000 候选几何审查；工艺与验证路线 |
| 2026-10-18 | [厚 SiO2 / Au100 / As2Se3 四聚体](reports/2026-10-18_topmetal_thick_substrate/README.md) | 结构纠正、R/T 光谱、衰减阈值对照、Q 值适用范围、服务器更新方法 |

**材料与网格更正：**旧默认 Au 拟合及旧版1000条服务器数据几乎丢失 Au 欧姆损耗，旧谱和权重保留为数值记录。10月24日的新层序报告使用2.2.0修正材料的新1000条数据，完成数值数据内的训练与验证；完整器件的金属局部网格尚未收敛，新批次仍为 `pipeline_validation`，详见报告中的适用范围及此前网格对照。

下载仓库后，可双击报告目录中的 `index.html` 在浏览器离线阅读。

# 单样本全域4 nm／金属2 nm参考

本项目只计算一个固定结构，核对金属局部网格以外的离散误差。不是新的1000样本任务，不接触原数据目录。

从下到上：厚SiO₂／Au100 nm／As₂Se₃四聚体；SiO₂延伸至下方PML。700–1700 nm，1000点，原生自动关断阈值1e-5；全域最大4 nm，金属局部2 nm。1个样本、1个求解进程、32线程。

## 在服务器运行

1. 用PyCharm打开本项目目录，解释器选择现有 `fdtd_gen`：`E:/anaconda3/envs/fdtd_gen/python.exe`。
2. 在PyCharm终端执行一次以下命令，安装随包附带的已固定版本，不需要Git，也不需CUDA：

```powershell
python -m pip install --no-deps --force-reinstall .\artifacts\deta_generator2-2.2.0-py3-none-any.whl
python run_reference.py check
```

3. 选择共享运行项 **01 Run single reference** 并运行。它先核对固定几何，再做原生材料、层序、网格预检，通过后自动计算一个样本。
4. 另开运行项 **02 Monitor reference**，每10秒显示任务记录和原生日志尾部；日志中的百分比、Auto Shutoff与剩余时间可直接查看。记录或日志不存在时会明确显示，没有把文件状态当作进程存活证明。

Lumerical API默认采用已提供的服务器路径 `E:/Lumerical/ANSYS Inc/v251/Lumerical/api/python/lumapi.py`，写在运行项环境变量中。关闭或中断后，重新运行01使用同一任务目录；成功样本不会再次求解。只启动一个01实例。

## 完成后带回

优先压缩整个项目目录；至少保留：

- `preflight.json`
- `data/samples/sample_000000.npz` 及同名CSV
- `data/projects/` 中的原生日志、网格/资源记录和FSP
- `data/manifest.json`、`job.json`

监视器显示success只说明任务记录成功，空间网格精度需要与已有金属局部2 nm结果进一步比较。此项目记录R/T/A，不额外记录旧研究的两张场平面，因此本次不能据此认证场增强的收敛。

## 已完成的本机预检

2026-10-28，本机v241原生材料、层序、网格预检通过：x/y实际最大3.9863 nm，z实际最大4.0000 nm，最小2.0000 nm。原生内存建议5.72 GiB，本机当时可用约2.2 GiB，未启动正式求解。服务器v251仍会重新执行原生预检；本机结果不替代服务器验证。

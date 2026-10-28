# 服务器单样本细网格参考启动包

2026-10-28，按用户选择改在Windows服务器运行。当前没有连接服务器的执行通道，需在服务器启动一次；不能将已备好的任务表述为已经开算。

本机原生预检已通过材料、层序、网格和PML监视面位置检查，内存建议为5.72 GiB，当时可用约2.2 GiB，因此未启动原生引擎。网格为全域4 nm、金属局部2 nm，几何保持与10月22日的 `au_both_2` 对照一致。

下载 [完整服务器项目ZIP](jc220_global4_metal2_server.zip)，解压到服务器独立目录后用PyCharm打开。包内含固定版本生成器wheel、原参考配置/材料表、单样本启动脚本、只读监视器和两个PyCharm运行项。详细操作见 [项目使用说明](server_project/README.md)。

原生成器代码与所有1000条样本目录均未修改。此前参考包的物理配置和材料表保持不变；新增的是服务器启动与监视入口。一个样本、一个求解进程、32线程。没有新光谱结果，也没有将预检当作网格收敛结论。

## 下载到服务器E盘

在服务器PowerShell执行，使用新的独立目录：

```powershell
$referenceDir = 'E:\CypherzZ\PythonProject\JC220_Global4_Metal2_Reference_20261028'
$referenceZip = 'E:\CypherzZ\PythonProject\jc220_global4_metal2_server.zip'
Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/CypherZzzyer05/Report/main/reports/2026-10-28_global4_reference_server/jc220_global4_metal2_server.zip' -OutFile $referenceZip
Expand-Archive -LiteralPath $referenceZip -DestinationPath $referenceDir
Set-Location $referenceDir
& 'E:\anaconda3\envs\fdtd_gen\python.exe' -m pip install --no-deps --force-reinstall .\artifacts\deta_generator2-2.2.0-py3-none-any.whl
```

随后用PyCharm打开 `$referenceDir`，选择现有fdtd_gen解释器，运行 **01 Run single reference**。另开 **02 Monitor reference** 查看进度。完成后把整个独立目录打包带回本机。

本次[本机原生预检](local_preflight.json)和[包与启动入口核验](verification.json)分别归档。预检采用本机v241；服务器v251必须重新原生检查，启动脚本已包含该步骤。

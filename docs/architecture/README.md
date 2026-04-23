# Architecture 文档组

这里放的是“系统怎么组成、为什么这样设计”的文档。

## 包含内容

| 文档 | 作用 |
|---|---|
| [system-architecture.md](/Users/tim/股市预测模型/docs/architecture/system-architecture.md) | 当前系统结构、优点、边界和演进方向 |
| [database-model.md](/Users/tim/股市预测模型/docs/architecture/database-model.md) | 数据分层、核心表语义和主键关系 |
| [DUAL_MACHINE_ARCHITECTURE.md](/Users/tim/股市预测模型/DUAL_MACHINE_ARCHITECTURE.md) | 双机协作、主库位置、运行分工和 Git 约束 |

## 适合什么时候看

- 你想修改模块边界
- 你想理解数据库为何这样分层
- 你想引入调度、并行、更多机器时

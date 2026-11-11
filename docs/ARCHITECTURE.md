# 当前架构（源码1.2-dev）

单核普通RP2040 Pico。电脑负责MIDI→最终主旋律JSON；板内负责文件校验、音高→指法和绝对时间调度。设备不读取电脑路径、不解析MIDI，也不依赖Windows实时发送每个音。发布v1.1仍是静态专用固件；新源码的构建/软件测试已通过，实机尚未验证。

| 层 | 文件 | 输入/输出 |
|---|---|---|
| 演示离线生成/回归 | tools/generate_song.py | 既有人声轨→原歌曲表、CSV、试听，附带内置fallback JSON字节 |
| 文件契约/校验 | src/melody.* | 不可变JSON字节→校验结果或LoadedSong |
| 指法 | src/fingering.h | B4–F6共19音→完整ControlState |
| 演奏 | src/player.h | SongView、当前绝对时间→ControlState |
| 控制器协议 | src/pro_controller.* | 状态和主机命令→64字节Pro报告 |
| 保存 | src/song_store.* | 校验文件→带CRC/代次的双槽Flash容器 |
| 上传协议 | src/upload_session.* | 有界命令行/分块→校验/提交/状态 |
| 配置USB/Flash | src/configuration.cpp、src/pico_song_flash.* | 独立CDC、分区内擦写 |
| 硬件循环 | src/main.cpp、src/usb_descriptors.cpp | 模式、USB任务、按钮、时钟、LED、报告 |

## 校验与调度

SongNote保存最终on/off微秒与MIDI pitch。LoadedSong持有有上限的事件数组；SongView不拥有数据。加载时先完整验证，再第二遍写入；输入须在整个调用期间不可变且不与输出重叠。没有堆上的JSON DOM或第二份完整事件表，metadata使用16层固定状态栈而非递归。

SongPlayer.start(view, now)将原点设为now+文件countdown_us；每轮update按绝对时间返回当前指法或中立，超过duration停止。暂停采样后直接定位当前事件，不补发已经错过的一串旧音。不通过整首sleep等待。时间线不再移调、变速、扣释放间隔或折八度。

歌曲时间uint32，设备校验最多3600000000微秒（60分钟）；系统时钟和origin用uint64，并防止开始时溢出。每音正时长、严格排序、至少40ms释放、全部落在duration内，每个音高必须有指法。4096事件与65536文件字节两个上限共同生效。

按钮去抖20ms、长按1秒；待机长按启动 `src/controller_join.h` 的非阻塞序列：L+R按住500ms、全松1000ms、L+R按住500ms、全松1000ms、A按住500ms、全松。相对64位绝对起点定位当前步骤，USB持续服务，不补发错过的步骤。持续按住只触发一次，松开不启动歌曲；序列中再次按下按钮会中止并消耗本次按压，USB挂载/卸载/挂起及协议未就绪也取消序列，避免重连后误发A。GP22与BOOTSEL等效，LED25保持原逻辑。GP21上电接地锁定配置模式。文件倒数可配置0–10秒。

## 指法与报告

内置oot-user-image-reference-v1完整19音表；C6使用图中第二套，其他音使用第一套，保留v1.1既有音的报告状态。机器参考含26种替代按法，尚无动态profile上传，替代按法也尚未逐套实机验证。

报告第3字节A位3、X位1、Y位0、R位6；第5字节十字键上位1、下位0、L位6。左摇杆位于第6–8字节，12位X/Y打包。默认2048，上3748，下348。十字键和摇杆独立，L3是点击而非方向。lookup_fingering显式返回缺指法，文件加载不会将缺失音静默变为休止。

详细按法见FULL_FINGERING_REFERENCE.md；编译表已与参考JSON的19个确定按法逐项核对。

## USB模式

播放模式沿用Pro HID IN/OUT、64字节端点和原0x057E/0x2009描述符；此模式不枚举CDC。配置模式单独枚举CDC，开发身份0xCAFE/0x4010，不提供Pro HID接口。模式在tusb_init前从GP21锁定，不在挂载中切换。

Pro协议参考GP2040-CE v0.7.12实现，但本工程独立，不是其分支：

- 主机0x80：识别、握手、波特率、关闭USB超时等。
- 主机0x01子命令：设备信息、模式、SPI校准、灯光等最小回复。
- 设备0x21子命令回复、0x81握手、0x30输入；成功发送后才推进计数，输入目标周期8ms。
- ready只表示本程序内部状态，不能证明主机接受；回复队列8项，满时丢弃新回复，GET_REPORT仍返回0，多项功能仅最小ACK。

## Flash/BOOTSEL协调

BOOTSEL采样函数在SRAM运行，关闭中断并暂时释放Flash CS，恢复后才返回。保持单核；配置模式不会调用BOOTSEL采样，也不会播放歌曲。

保存只在配置模式，通过固定分区内的对齐接口擦写；写入时关中断调用SDK Flash函数，操作后恢复并服务USB。非当前槽的数据和CRC完整后最后写头提交，冷启动同时验证两个槽及JSON，选择有效较新槽。固件链接断言禁止跨入歌曲区。播放中不写Flash。

普通2MiB Pico最后136KiB为歌曲区；详细容器、命令、CRC、容量、内存实测与实机验收见RUNTIME_CONFIGURATION.md。无有效保存文件时加载明确的内置演示，仍需用户按钮开始。

## 验证边界

本轮full/first native各8/8（开启MIDI导入测试，含新增controller_join时序/报告测试）；Arm GNU14.2.Rel1（GCC14.2.1）+ SDK2.1.1构建通过，两份新UF2逐块核验，开发下载文件及SHA256同步。详情见VALIDATION.md。CLI/Flash镜像进程模拟可证明协议、回退和独立调度代码；不能证明真实USB枚举、Flash掉电电气行为或游戏音乐输入。MIDI导入CLI已实现，下一阶段仍是实机验收和后续GUI。

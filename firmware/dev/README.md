# 可上传歌曲的开发测试固件

下载 [Pico_Ocarina_Configurable_v1_2_dev.uf2](Pico_Ocarina_Configurable_v1_2_dev.uf2)，按 [使用说明](../../开始使用.md) 刷入、上传歌曲和播放。

适用普通 Raspberry Pi Pico（RP2040）。初次使用内置《皇后大道东》完整版；上传其他合法JSON后，播放保存的歌曲。日常换歌不必重编译或重刷固件。

本次更新待机长按 BOOTSEL 约1秒的换手柄操作：L+R按住半秒 → 松开1秒 → L+R按住半秒 → 松开1秒 → A按住半秒 → 全松。长按只执行一次，执行中再次按可中止；USB断连/挂起会取消。要使用新操作，已刷过旧测试版的板子也需重刷这份更新后的UF2。

这是1.2-dev测试版：已通过软件测试、RP2040编译和UF2文件核验，尚未在真实Pico、Windows USB和Switch游戏上验证。它与上一级目录的v1.1内置歌曲固件分开放置。

校验和见 [SHA256SUMS.txt](SHA256SUMS.txt)，构建与验证记录见 [VALIDATION.md](../../VALIDATION.md)。

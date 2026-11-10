#pragma once
// Latched from GP21 before USB initialization, never switched while mounted.
extern bool ocarina_config_mode;
void configuration_task();

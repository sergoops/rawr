#pragma once

#include <android/log.h>

#include <cstdint>
#include <ctime>

namespace rawrcam::capture::multiframe {

inline double rextureMonoMs() noexcept {
    timespec ts{};
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return static_cast<double>(ts.tv_sec) * 1000.0 + static_cast<double>(ts.tv_nsec) / 1e6;
}

inline void rextureTiming(std::uint64_t requestId, const char* stage) noexcept {
    __android_log_print(ANDROID_LOG_INFO, "RawrCamNative", "REXTURE_TIMING requestId=%llu stage=%s monoMs=%.3f",
                        static_cast<unsigned long long>(requestId), stage, rextureMonoMs());
}

}  // namespace rawrcam::capture::multiframe

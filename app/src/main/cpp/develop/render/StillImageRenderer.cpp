#include "develop/render/StillImageRenderer.h"

#include <android/log.h>

#include <chrono>
#include <exception>

#include "develop/render/StillRenderSequence.h"
namespace rawrcam::develop::rendered {

StillImageRenderer::StillImageRenderer(std::string filesDir, Diagnostic diagnostic)
    : filesDir_(std::move(filesDir)), diagnostic_(std::move(diagnostic)), resources_(filesDir_, diagnostic_) {}
StillImageRenderer::~StillImageRenderer() { reset(); }

void StillImageRenderer::setAssetManager(AAssetManager* assetManager) noexcept {
    resources_.setAssetManager(assetManager);
}

void StillImageRenderer::shutdownFilm() noexcept {
    joinPrepareWorker();
    joinWorker();
    resources_.destroyFilm();
}

bool StillImageRenderer::busy() const noexcept {
    std::lock_guard<std::mutex> lock(stateMutex_);
    return busy_ || prepareBusy_ || prepared_;
}

void StillImageRenderer::clearPreparedLocked() noexcept {
    prepared_ = false;
    prepareBusy_ = false;
    preparedEngineBuildMs_ = 0.0;
    preparedSetupMs_ = 0.0;
    preparedRequestId_ = 0;
    preparedWidth_ = 0;
    preparedHeight_ = 0;
    preparedUltraHdr_ = false;
}

bool StillImageRenderer::prepare(const rawrcam::vulkan::VulkanContext& context, std::mutex& queueSubmitMutex,
                                 const RenderedStillContext& rendered, VkQueue queueOverride,
                                 std::mutex* queueSubmitMutexOverride) {
    if (!context.device() || !context.physicalDevice() || !context.queue() || rendered.requestId == 0 ||
        rendered.width == 0 || rendered.height == 0)
        return false;
    joinPrepareWorker();
    {
        std::lock_guard<std::mutex> lock(stateMutex_);
        if (busy_ || prepareBusy_ || prepared_ || completion_ || resources_.holdsOutput()) return false;
        prepareBusy_ = true;
        prepareError_.clear();
        preparedEngineBuildMs_ = 0.0;
        preparedSetupMs_ = 0.0;
        preparedRequestId_ = rendered.requestId;
        preparedWidth_ = rendered.width;
        preparedHeight_ = rendered.height;
        preparedUltraHdr_ = rendered.ultraHdrEnabled;
    }
    const RenderDeviceContext device{context.physicalDevice(),
                                     context.device(),
                                     queueOverride ? queueOverride : context.queue(),
                                     context.queueFamily(),
                                     queueSubmitMutexOverride ? queueSubmitMutexOverride : &queueSubmitMutex};
    try {
        prepareWorker_ = std::thread([this, device, rendered]() {
            const auto begin = std::chrono::steady_clock::now();
            try {
                resources_.bind(device);
                resources_.createPixels(rendered);
                const double engineBuildMs = resources_.prepareEngines(rendered);
                const double setupMs =
                    std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - begin).count();
                {
                    std::lock_guard<std::mutex> lock(stateMutex_);
                    preparedEngineBuildMs_ = engineBuildMs;
                    preparedSetupMs_ = setupMs;
                    prepared_ = true;
                    prepareBusy_ = false;
                }
                const std::string line = "STILL_RENDER_PREPARE requestId=" + std::to_string(rendered.requestId) +
                                         " engineBuildMs=" + std::to_string(engineBuildMs) +
                                         " setupMs=" + std::to_string(setupMs);
                __android_log_print(ANDROID_LOG_INFO, "RawrCamNative", "%s", line.c_str());
                emit(line);
            } catch (const std::exception& e) {
                {
                    std::lock_guard<std::mutex> lock(stateMutex_);
                    prepareError_ = e.what();
                    prepareBusy_ = false;
                    prepared_ = false;
                }
                const std::string line =
                    "STILL_RENDER_PREPARE_FAIL requestId=" + std::to_string(rendered.requestId) + " error=" + e.what();
                __android_log_print(ANDROID_LOG_ERROR, "RawrCamNative", "%s", line.c_str());
                emit(line);
            } catch (...) {
                {
                    std::lock_guard<std::mutex> lock(stateMutex_);
                    prepareError_ = "unknown";
                    prepareBusy_ = false;
                    prepared_ = false;
                }
                const std::string line =
                    "STILL_RENDER_PREPARE_FAIL requestId=" + std::to_string(rendered.requestId) + " error=unknown";
                __android_log_print(ANDROID_LOG_ERROR, "RawrCamNative", "%s", line.c_str());
                emit(line);
            }
        });
    } catch (...) {
        std::lock_guard<std::mutex> lock(stateMutex_);
        prepareBusy_ = false;
        prepareError_ = "thread_create_failed";
        return false;
    }
    return true;
}

bool StillImageRenderer::start(const rawrcam::vulkan::VulkanContext& context, std::mutex& queueSubmitMutex,
                               const RenderedStillContext& rendered, VkImage sourceImage, VkImageView sourceView,
                               VkImage clipStateImage, VkImageView clipStateView, VkQueue queueOverride,
                               std::mutex* queueSubmitMutexOverride) {
    if (!context.device() || !context.physicalDevice() || !context.queue() || !sourceImage || !sourceView ||
        rendered.requestId == 0 || rendered.width == 0 || rendered.height == 0)
        return false;
    joinPrepareWorker();
    bool usePrepared = false;
    double preparedEngineBuildMs = 0.0;
    bool discardPrepared = false;
    {
        std::lock_guard<std::mutex> lock(stateMutex_);
        if (busy_ || prepareBusy_ || completion_) return false;
        if (prepared_) {
            const bool match = preparedRequestId_ == rendered.requestId && preparedWidth_ == rendered.width &&
                               preparedHeight_ == rendered.height &&
                               preparedUltraHdr_ == rendered.ultraHdrEnabled;
            prepared_ = false;
            if (match && resources_.holdsOutput()) {
                usePrepared = true;
                preparedEngineBuildMs = preparedEngineBuildMs_;
            } else {
                discardPrepared = true;
            }
        } else if (!prepareError_.empty()) {
            discardPrepared = true;
        } else if (resources_.holdsOutput()) {
            return false;
        }
        prepareError_.clear();
        busy_ = true;
    }
    if (discardPrepared) resources_.reset();
    const RenderDeviceContext device{context.physicalDevice(),
                                     context.device(),
                                     queueOverride ? queueOverride : context.queue(),
                                     context.queueFamily(),
                                     queueSubmitMutexOverride ? queueSubmitMutexOverride : &queueSubmitMutex};
    resources_.bind(device);

    try {
        worker_ = std::thread([this, device, rendered, sourceImage, sourceView, clipStateImage, clipStateView,
                               usePrepared, preparedEngineBuildMs]() {
            auto done = executeStillRender(resources_, commands_, device, rendered, sourceImage, sourceView,
                                           clipStateImage, clipStateView, filesDir_,
                                           [this](const std::string& line) { emit(line); }, usePrepared,
                                           preparedEngineBuildMs);
            {
                std::lock_guard<std::mutex> lock(stateMutex_);
                completion_ = done;
                busy_ = false;
            }
        });
    } catch (...) {
        std::lock_guard<std::mutex> lock(stateMutex_);
        busy_ = false;
        return false;
    }
    return true;
}

std::optional<RenderedStillCompletion> StillImageRenderer::pollCompletion() {
    std::optional<RenderedStillCompletion> out;
    {
        std::lock_guard<std::mutex> lock(stateMutex_);
        if (!completion_) return std::nullopt;
        out = completion_;
        completion_.reset();
    }
    joinWorker();
    return out;
}
void StillImageRenderer::joinWorker() noexcept {
    if (worker_.joinable()) worker_.join();
}
void StillImageRenderer::joinPrepareWorker() noexcept {
    if (prepareWorker_.joinable()) prepareWorker_.join();
}
void StillImageRenderer::releasePixels() noexcept {
    joinPrepareWorker();
    joinWorker();
    {
        std::lock_guard<std::mutex> lock(stateMutex_);
        clearPreparedLocked();
        prepareError_.clear();
    }
    commands_.reset();
    resources_.releasePixels();
}

void StillImageRenderer::reset() noexcept {
    joinPrepareWorker();
    joinWorker();
    {
        std::lock_guard<std::mutex> lock(stateMutex_);
        busy_ = false;
        completion_.reset();
        clearPreparedLocked();
        prepareError_.clear();
    }
    commands_.reset();
    resources_.reset();
}

void StillImageRenderer::emit(const std::string& line) const {
    if (diagnostic_) diagnostic_(line);
}

}  // namespace rawrcam::develop::rendered

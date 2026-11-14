#include "capture/single/SingleFrameCaptureJournal.h"

#include <thread>
#include <utility>

#include "capture/persistence/ProcessingRecipe.h"
#include "diagnostics/logging/RuntimeTraceRecorder.h"

namespace rawrcam::capture {
void SingleFrameCaptureJournal::setAdmission(persistence::CaptureReservation reservation, std::string path) {
    reservation_ = std::move(reservation);
    durablePath_ = std::move(path);
}
void SingleFrameCaptureJournal::freeze(const encoding::dng::DngCaptureContext& dng, const JpegCaptureRequest* jpeg) {
    frozen_ = {};
    // Copies never carry the output descriptors (encoding::OutputFd).
    frozen_.dng = dng;
    frozen_.jpegRequested = jpeg != nullptr;
    if (jpeg) frozen_.jpeg = *jpeg;
}
void SingleFrameCaptureJournal::commit(SingleFrameSnapshot& deferred) {
    if (frozen_.dng.captureTone) {
        deferred.tonemapParams = *frozen_.dng.captureTone;
        deferred.tonemapParams.aePostGain = deferred.aePostGain;
    }
    if (frozen_.dng.captureFilm) {
        deferred.filmEnabled = frozen_.dng.captureFilmEnabled;
        deferred.filmLook = *frozen_.dng.captureFilm;
    }
    persistence::CaptureJob job;
    job.frame = std::move(*deferred.frame);
    frozen_.dng.resolvedRecipe = persistence::resolvedRecipe(deferred.tonemapParams, deferred.aePostGain,
                                                             deferred.filmEnabled, deferred.filmLook);
    job.dng = frozen_.dng;
    if (frozen_.jpegRequested) job.jpeg = frozen_.jpeg;
    job.jpegRequested = frozen_.jpegRequested;
    job.tone = deferred.tonemapParams;
    job.gain = deferred.aePostGain;
    job.filmEnabled = deferred.filmEnabled;
    job.film = deferred.filmLook;
    // The journal is recovery input, not an output. Write/rename it now so the
    // raw can leave RAM, then flush it in the background while the still is
    // developed. A process crash still finds the renamed file; only a power
    // loss before the async fsync can lose the recovery copy.
    persistence::saveWithoutSync(durablePath_, job);
    try {
        std::thread([path = durablePath_] {
            try {
                persistence::syncJob(path);
            } catch (...) {
            }
        }).detach();
    } catch (...) {
        persistence::syncJob(durablePath_);
    }
    if (!keepRawResident_.load()) {
        // Waiting payloads leave RAM; the worker reloads them when their turn comes.
        job.frame.raw16.clear();
        job.frame.raw16.shrink_to_fit();
        reservation_.reset();
    }
    *deferred.frame = std::move(job.frame);
    diagnostics::RuntimeTraceRecorder::instance().record(diagnostics::RuntimeTraceStage::StillDurable,
                                                         deferred.frame->timestampNs, deferred.frame->requestId);
    emit("STILL_JOB_DURABLE path=" + durablePath_);
}
void SingleFrameCaptureJournal::reloadRaw(SingleFrameSnapshot& snapshot) const {
    if (snapshot.frame->raw16.empty()) {
        auto stored = persistence::load(durablePath_);
        snapshot.frame->raw16 = std::move(stored.frame.raw16);
    }
}
}  // namespace rawrcam::capture

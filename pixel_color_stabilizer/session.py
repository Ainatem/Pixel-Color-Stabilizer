"""Preview/apply/undo state independent of GUI and disk locations."""
from .core import temporal_mode
from .media import Animation


class Session:
    def __init__(self, animation):
        self.current = animation
        self.preview = None
        self.report = None
        self.history = []

    def invalidate(self):
        self.preview = self.report = None

    def make_preview(self, **params):
        self.invalidate()
        frames, report = temporal_mode(self.current.frames, **params)
        self.preview = Animation(frames, self.current.durations.copy(), self.current.operations + [report])
        self.report = report
        return report

    def apply(self):
        if self.preview is None:
            raise ValueError('Generate a preview before applying.')
        self.history.append(self.current)
        self.current = self.preview
        self.invalidate()

    def undo(self):
        if not self.history:
            raise ValueError('Nothing to undo in this session.')
        self.current = self.history.pop()
        self.invalidate()

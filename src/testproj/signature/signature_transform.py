import inspect


class SigTransform:
    def __init__(self, sig: inspect.Signature):
        self.signature = sig

    def process(self) -> inspect.Signature:
        return self.signatures


identity = SigTransform()


# def test_

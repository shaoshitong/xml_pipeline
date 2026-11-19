"""Honor Qwen3.8's tokenizer-declared thinking-to-tool boundary in SGLang 0.5.10."""


def install():
    from sglang.srt.parser.reasoning_parser import Qwen3Detector, ReasoningParser

    class Qwen38Detector(Qwen3Detector):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # tokenizer_config.json closes reasoning at </think> OR <tool_call>.
            # Reuse SGLang's existing tool-interruption implementation; retain
            # the generated tool text verbatim for the qwen3_coder tool parser.
            self.tool_start_token = "<tool_call>"

    ReasoningParser.DetectorMap["qwen3"] = Qwen38Detector

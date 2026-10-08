"""LLM-as-judge: grades one answer for correctness and for claims its evidence doesn't support."""

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.nodes import format_sources
from app.llm import get_model
from eval.dataset import Question
from eval.systems import SystemOutput

JUDGE_PROMPT = """You grade answers from an AI assistant about the internal documents of \
Brindlewave, a company that makes Tally (warehouse sensors and software).

You get the question, a reference answer written by a human, the EVIDENCE the assistant had \
(numbered document passages and tool results; possibly none), and the assistant's answer.

1. verdict: compare the answer with the reference answer.
   - "correct": states the reference answer's key facts (extra correct detail is fine)
   - "partially_correct": some key facts right, others missing or wrong
   - "incorrect": wrong; or gives an answer where the reference says it's not in the documents
   - "refused": says it can't find or doesn't know the answer, without giving a substantive answer
2. unsupported_claims: list every specific factual claim in the answer that the EVIDENCE does not \
support. Be strict and literal: a claim counts as supported only if the evidence states it or it \
follows directly (correct arithmetic on evidence numbers counts as supported). Saying that \
information is unavailable is not a claim. If there is no evidence, every specific claim about \
Brindlewave or its products is unsupported. Return [] if everything is supported."""


class Judgement(BaseModel):
    verdict: Literal["correct", "partially_correct", "incorrect", "refused"]
    unsupported_claims: list[str] = Field(description="claims not supported by the evidence; [] if none")
    explanation: str = Field(description="one or two sentences justifying the verdict")


def judge(question: Question, output: SystemOutput, model: str) -> Judgement:
    evidence = format_sources(output.sources) if output.sources else ""
    if output.tool_results:
        evidence += "\n\nTool results:\n" + "\n".join(f"- {t}" for t in output.tool_results)
    message = (
        f"QUESTION:\n{question.question}\n\n"
        f"REFERENCE ANSWER:\n{question.answer}\n\n"
        f"EVIDENCE:\n{evidence.strip() or '(none: the assistant saw no documents)'}\n\n"
        f"ASSISTANT'S ANSWER:\n{output.answer}"
    )
    return get_model(model).with_structured_output(Judgement).invoke(
        [SystemMessage(JUDGE_PROMPT), HumanMessage(message)]
    )

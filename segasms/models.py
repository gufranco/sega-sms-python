from __future__ import annotations

from dataclasses import dataclass

from smsmapper import models as consoles

PROCESSOR = "z80"

PAL_REGION = "europe"

PAL = "pal"

NTSC = "ntsc"


@dataclass(frozen=True, slots=True)
class Model:
    console: str
    vdp: str
    processor: str

    @property
    def name(self) -> str:
        return self.console

    @property
    def aliases(self) -> tuple[str, ...]:
        return consoles.MODELS[self.console].aliases


MODELS: dict[str, Model] = {
    model.console: model
    for model in (
        Model("mark-iii", "315-5124", PROCESSOR),
        Model("sms", "315-5124", PROCESSOR),
        Model("sms2", "315-5246", PROCESSOR),
        Model("gg", "315-5378", PROCESSOR),
    )
}


def lookup(name: str | None) -> Model:
    return MODELS[consoles.lookup(name).name]


def vdp_part(name: str | None) -> str:
    return lookup(name).vdp


def vdp_region(name: str | None, region: str) -> str:
    console = consoles.lookup(name)
    return PAL if region == PAL_REGION and not console.handheld else NTSC

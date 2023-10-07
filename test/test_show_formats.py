import struct

from pytest import fixture, raises
from typing import List

from flockwave.server.show.formats import (
    RTHPlanEncoder,
    SkybrushBinaryFileBlock,
    SkybrushBinaryFileFeatures,
    SkybrushBinaryShowFile,
    SkybrushBinaryFormatBlockType,
)
from flockwave.server.show.rth_plan import RTHAction, RTHPlan, RTHPlanEntry


SIMPLE_SKYB_FILE_V1 = (
    # Header, version 1
    b"skyb\x01"
    # Trajectory block starts here
    b"\x01$\x00\n\x00\x00\x00\x00\x00\x00\x00\x00\x10\x10'\xe8\x03"
    b"\x01\x10'\xe8\x03\x04\x10'\xe8\x03\x05\x10'\x00\x00\x00\x00"
    b"\x10\x10'\x00\x00"
    # Comment block starts here
    b"\x03\x13\x00this is a test file"
)


SIMPLE_SKYB_FILE_V2 = (
    # Header, version 2, feature flags
    b"skyb\x02\x01"
    # Checksum
    b"(\xda\xd0\x83"
    # Trajectory block starts here
    b"\x01$\x00\n\x00\x00\x00\x00\x00\x00\x00\x00\x10\x10'\xe8\x03"
    b"\x01\x10'\xe8\x03\x04\x10'\xe8\x03\x05\x10'\x00\x00\x00\x00"
    b"\x10\x10'\x00\x00"
    # Comment block starts here
    b"\x03\x13\x00this is a test file"
)


@fixture
def plan() -> RTHPlan:
    plan = RTHPlan()

    entry = RTHPlanEntry(time=0, action=RTHAction.LAND)
    plan.add_entry(entry)

    entry = RTHPlanEntry(
        time=15,
        action=RTHAction.GO_TO_KEEPING_ALTITUDE_AND_LAND,
        target=(30, 40),
        duration=50,
        post_delay=5,
    )
    plan.add_entry(entry)

    entry = RTHPlanEntry(
        time=45,
        action=RTHAction.GO_TO_KEEPING_ALTITUDE_AND_LAND,
        target=(-40, -30),
        duration=50,
        pre_delay=2,
    )
    plan.add_entry(entry)

    entry = RTHPlanEntry(
        time=65,
        action=RTHAction.GO_TO_KEEPING_ALTITUDE_AND_LAND,
        target=(30, 40),
        duration=30,
    )
    plan.add_entry(entry)

    entry = RTHPlanEntry(
        time=80,
        action=RTHAction.GO_TO_KEEPING_ALTITUDE_AND_LAND,
        target=(30, 40),
        duration=20,
    )
    plan.add_entry(entry)

    entry = RTHPlanEntry(time=105, action=RTHAction.LAND)
    plan.add_entry(entry)

    return plan


ENCODED_RTH_PLAN_WITH_PROPOSED_SCALING_FACTOR = (
    # Scaling factor
    b"\x02"
    # Number of points
    b"\x02\x00"
    # Point 1: (30, 40)
    b"\x98\x3a\x20\x4e"
    # Point 2: (-40, -30)
    b"\xe0\xb1\x68\xc5"
    # Number of entries
    b"\x06\x00"
    # Entry 1: time=0, land
    b"\x10\x00"
    # Entry 2: time since previous = 15, go to (30, 40) in 50s, post-delay=5
    b"\x21\x0f\x00\x32\x05"
    # Entry 3: time since previous = 30, go to (-40, -30) in 50s, pre-delay=2
    b"\x22\x1e\x01\x32\x02"
    # Entry 4: time since previous = 20, go to (30, 40) in 30s
    b"\x20\x14\x00\x1e"
    # Entry 5: time since previous = 15, same as previous but in 20s
    b"\x00\x0f\x14"
    # Entry 6: time since previous = 25, land
    b"\x10\x19"
)

ENCODED_RTH_PLAN_WITH_SCALING_FACTOR_10 = (
    # Scaling factor
    b"\x0a"
    # Number of points
    b"\x02\x00"
    # Point 1: (30, 40)
    b"\xb8\x0b\xa0\x0f"
    # Point 2: (-40, -30)
    b"\x60\xf0\x48\xf4"
    # Number of entries
    b"\x06\x00"
    # Entry 1: time=0, land
    b"\x10\x00"
    # Entry 2: time since previous = 15, go to (30, 40) in 50s, post-delay=5
    b"\x21\x0f\x00\x32\x05"
    # Entry 3: time since previous = 30, go to (-40, -30) in 50s, pre-delay=2
    b"\x22\x1e\x01\x32\x02"
    # Entry 4: time since previous = 20, go to (30, 40) in 30s
    b"\x20\x14\x00\x1e"
    # Entry 5: time since previous = 15, same as previous but in 20s
    b"\x00\x0f\x14"
    # Entry 6: time since previous = 25, land
    b"\x10\x19"
)


@fixture
def too_large_plan() -> RTHPlan:
    plan = RTHPlan()

    entry = RTHPlanEntry(time=0, action=RTHAction.LAND)
    plan.add_entry(entry)

    entry = RTHPlanEntry(
        time=15,
        action=RTHAction.GO_TO_KEEPING_ALTITUDE_AND_LAND,
        target=(30000, 40000),
        duration=50,
        post_delay=5,
    )
    plan.add_entry(entry)

    return plan


class TestSkybrushBinaryFileFormat:
    async def test_reading_blocks_version_1(self):
        async with SkybrushBinaryShowFile.from_bytes(SIMPLE_SKYB_FILE_V1) as f:
            blocks = await f.read_all_blocks()

            assert f.version == 1
            assert not f.features
            assert len(blocks) == 2

            assert blocks[0].type == SkybrushBinaryFormatBlockType.TRAJECTORY
            data = await blocks[0].read()
            assert data == (
                b"\n\x00\x00\x00\x00\x00\x00\x00\x00\x10\x10'\xe8\x03"
                b"\x01\x10'\xe8\x03\x04\x10'\xe8\x03\x05\x10'\x00\x00\x00\x00"
                b"\x10\x10'\x00\x00"
            )

            assert blocks[1].type == SkybrushBinaryFormatBlockType.COMMENT
            data = await blocks[1].read()
            assert data == (b"this is a test file")

    async def test_reading_blocks_version_2(self):
        async with SkybrushBinaryShowFile.from_bytes(SIMPLE_SKYB_FILE_V2) as f:
            blocks = await f.read_all_blocks()

            assert f.version == 2
            assert f.features == SkybrushBinaryFileFeatures.CRC32
            assert len(blocks) == 2

            assert blocks[0].type == SkybrushBinaryFormatBlockType.TRAJECTORY
            data = await blocks[0].read()
            assert data == (
                b"\n\x00\x00\x00\x00\x00\x00\x00\x00\x10\x10'\xe8\x03"
                b"\x01\x10'\xe8\x03\x04\x10'\xe8\x03\x05\x10'\x00\x00\x00\x00"
                b"\x10\x10'\x00\x00"
            )

            assert blocks[1].type == SkybrushBinaryFormatBlockType.COMMENT
            data = await blocks[1].read()
            assert data == (b"this is a test file")

    async def test_reading_blocks_version_2_invalid_crc(self):
        data = SIMPLE_SKYB_FILE_V2[:6] + b"\x00" + SIMPLE_SKYB_FILE_V2[7:]
        with raises(RuntimeError, match="CRC error"):
            async with SkybrushBinaryShowFile.from_bytes(data) as f:
                await f.read_all_blocks()

    async def test_adding_blocks_version_1(self):
        async with SkybrushBinaryShowFile.create_in_memory(version=1) as f:
            await f.add_block(
                SkybrushBinaryFormatBlockType.TRAJECTORY,
                b"\n\x00\x00\x00\x00\x00\x00\x00\x00\x10\x10'\xe8\x03"
                b"\x01\x10'\xe8\x03\x04\x10'\xe8\x03\x05\x10'\x00\x00\x00\x00"
                b"\x10\x10'\x00\x00",
            )
            await f.add_comment("this is a test file")
            await f.finalize()
            assert f.get_contents() == SIMPLE_SKYB_FILE_V1

    async def test_adding_blocks_version_2_with_checksum(self):
        async with SkybrushBinaryShowFile.create_in_memory(version=2) as f:
            await f.add_block(
                SkybrushBinaryFormatBlockType.TRAJECTORY,
                b"\n\x00\x00\x00\x00\x00\x00\x00\x00\x10\x10'\xe8\x03"
                b"\x01\x10'\xe8\x03\x04\x10'\xe8\x03\x05\x10'\x00\x00\x00\x00"
                b"\x10\x10'\x00\x00",
            )
            await f.add_comment("this is a test file")
            await f.finalize()
            assert f.get_contents() == SIMPLE_SKYB_FILE_V2

    async def test_adding_block_that_is_too_large(self):
        async with SkybrushBinaryShowFile.create_in_memory() as f:
            with raises(ValueError, match="body too large"):
                await f.add_block(
                    SkybrushBinaryFormatBlockType.TRAJECTORY,
                    b"\x00" * 128 * 1024,
                )

    async def test_invalid_magic_marker(self):
        with raises(RuntimeError, match="expected Skybrush binary file header"):
            async with SkybrushBinaryShowFile.from_bytes(b"not-a-skyb-file") as f:
                await f.read_all_blocks()

    async def test_invalid_version(self):
        with raises(RuntimeError, match="version"):
            async with SkybrushBinaryShowFile.from_bytes(b"skyb\xff") as f:
                await f.read_all_blocks()

    async def test_adding_rth_plan_block(self, plan: RTHPlan):
        async with SkybrushBinaryShowFile.create_in_memory() as f:
            await f.add_rth_plan(plan)
            await f.finalize()
            contents = f.get_contents()

        blocks: List[SkybrushBinaryFileBlock] = []
        async with SkybrushBinaryShowFile.from_bytes(contents) as f:
            blocks = await f.read_all_blocks()

            assert len(blocks) == 1
            assert blocks[0].type == SkybrushBinaryFormatBlockType.RTH_PLAN
            assert (
                await blocks[0].read()
            ) == ENCODED_RTH_PLAN_WITH_PROPOSED_SCALING_FACTOR

    async def test_adding_rth_plan_block_too_large(self, too_large_plan: RTHPlan):
        async with SkybrushBinaryShowFile.create_in_memory() as f:
            with raises(RuntimeError):
                await f.add_rth_plan(too_large_plan)


class TestRTHPlanEncoder:
    async def test_encoding_basic_plan(self, plan: RTHPlan):
        encoder = RTHPlanEncoder(scale=10)
        data = encoder.encode(plan)
        assert data == ENCODED_RTH_PLAN_WITH_SCALING_FACTOR_10

    async def test_encoding_basic_plan_default_scaling_factor(self, plan: RTHPlan):
        encoder = RTHPlanEncoder(scale=plan.propose_scaling_factor())
        data = encoder.encode(plan)
        assert data == ENCODED_RTH_PLAN_WITH_PROPOSED_SCALING_FACTOR

    async def test_encoding_basic_plan_with_invalid_scale(self, plan: RTHPlan):
        encoder = RTHPlanEncoder(scale=1)
        with raises(struct.error):
            encoder.encode(plan)

    async def test_encoding_plan_with_negative_step_duration(self):
        plan = RTHPlan()
        entry = RTHPlanEntry(
            time=15,
            action=RTHAction.GO_TO_KEEPING_ALTITUDE_AND_LAND,
            target=(30, 40),
            duration=-50,
            post_delay=5,
        )
        plan.add_entry(entry)
        with raises(ValueError, match="negative duration: -50"):
            RTHPlanEncoder(scale=plan.propose_scaling_factor()).encode(plan)

    async def test_encoding_plan_with_unknown_action(self):
        plan = RTHPlan()
        entry = RTHPlanEntry(
            time=15,
            action="no-such-action",  # type: ignore
            target=(30, 40),
            duration=-50,
            post_delay=5,
        )
        plan.add_entry(entry)
        with raises(ValueError, match="unknown RTH action: no-such-action"):
            RTHPlanEncoder(scale=100).encode(plan)

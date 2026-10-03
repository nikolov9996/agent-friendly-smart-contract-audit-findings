---
id: 25069
severity: "Medium"
---

# Integer Truncation in Incentive Rate Permanently Locks Unstreamed Rewards

## Description



## Proof of Concept

I write a poc in `deli-swap-contracts/test/unit/IncentiveGaugeRoundingDust.t.sol` run this command to test`forge test --match-contract IncentiveGaugeRoundingDustTest -vvv `

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import {Test} from "forge-std/Test.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

import {IncentiveGauge} from "src/IncentiveGauge.sol";
import {MockPoolManager} from "test/mocks/MockPoolManager.sol";
import {IPoolManager} from "@uniswap/v4-core/src/interfaces/IPoolManager.sol";

import {PoolKey} from "@uniswap/v4-core/src/types/PoolKey.sol";
import {PoolId, PoolIdLibrary} from "@uniswap/v4-core/src/types/PoolId.sol";
import {Currency} from "@uniswap/v4-core/src/types/Currency.sol";
import {IHooks} from "@uniswap/v4-core/src/interfaces/IHooks.sol";

import {EfficientHashLib} from "solady/utils/EfficientHashLib.sol";
import {IPositionManagerAdapter} from "src/interfaces/IPositionManagerAdapter.sol";
import {PositionInfo} from "v4-periphery/src/libraries/PositionInfoLibrary.sol";

contract USDC6 is IERC20 {
    string public name = "Mock USDC";
    string public symbol = "USDC";
    uint8 public constant decimals = 6;
    mapping(address => uint256) public override balanceOf;
    mapping(address => mapping(address => uint256)) public override allowance;
    uint256 public override totalSupply;

    function transfer(address to, uint256 amount) external override returns (bool) {
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        emit Transfer(msg.sender, to, amount);
        return true;
    }
    function approve(address spender, uint256 amount) external override returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }
    function transferFrom(address from, address to, uint256 amount) external override returns (bool) {
        uint256 allowed = allowance[from][msg.sender];
        if (allowed != type(uint256).max) allowance[from][msg.sender] = allowed - amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
        return true;
    }
    function mint(address to, uint256 amount) external {
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }
}

contract IncentiveGaugeRoundingDustTest is Test {
    using PoolIdLibrary for PoolKey;

    MockPoolManager pm;
    IncentiveGauge gauge;
    USDC6 usdc;

    address owner = address(this);
    address hook = address(this);
    address funder = address(0xF00D);
    address lpOwner = address(0xDEADBEEF);

    PoolKey key;
    PoolId pid;

    function setUp() public {
        pm = new MockPoolManager();
        // Adapter is not used in this PoC; pass this contract address
        gauge = new IncentiveGauge(IPoolManager(address(pm)), IPositionManagerAdapter(address(this)), hook);
        usdc = new USDC6();

        // Build a minimal PoolKey
        key = PoolKey({
            currency0: Currency.wrap(address(0xC0)),
            currency1: Currency.wrap(address(0xC1)),
            fee: 0,
            tickSpacing: 60,
            hooks: IHooks(address(0))
        });
        pid = key.toId();

        // Initialize pool via hook and set whitelist
        gauge.initPool(key, 0);
        gauge.setWhitelist(IERC20(address(usdc)), true);

        // Prepare PoolManager slot0 for updates
        pm.setPoolSlot0(PoolId.unwrap(pid), 79228162514264337593543950336, 0); // sqrtPriceX96=1, tick=0

        // Fund depositor
        usdc.mint(funder, 100_000_000); // 100 USDC with 6 decimals
        vm.prank(funder);
        usdc.approve(address(gauge), type(uint256).max);
    }

    function test_PoC_incentive_dust_is_discarded_and_locked() public {
        uint256 amount = 100_000_000; // 100 USDC (6 decimals)

        // Create incentive (pulls tokens)
        vm.prank(funder);
        gauge.createIncentive(key, IERC20(address(usdc)), amount);

        // Verify integer division on rate
        (uint256 rate,, uint256 remainingBefore) = gauge.incentiveData(pid, IERC20(address(usdc)));
        assertEq(remainingBefore, amount, "remaining should equal amount at start");
        uint256 expectedRate = amount / 604800; // WEEK seconds
        assertEq(rate, expectedRate, "rate should be floor(amount/WEEK)");
        uint256 dust = amount - expectedRate * 604800;
        assertGt(dust, 0, "dust must be > 0 for non-multiple amounts");

        // Advance to after finish and update once via hook
        vm.warp(block.timestamp + 604800 + 1);
        gauge.pokePool(key);

        // After finish, incentive is deactivated and remaining is set to 0
        (uint256 rateAfter,, uint256 remainingAfter) = gauge.incentiveData(pid, IERC20(address(usdc)));
        assertEq(rateAfter, 0, "rewardRate should be 0 after finish");
        assertEq(remainingAfter, 0, "remaining set to 0 (dust discarded)");

        // Contract still holds the full amount (no positions to claim)
        uint256 bal = usdc.balanceOf(address(gauge));
        assertEq(bal, amount, "all tokens remain in contract; dust is irrecoverable");
    }

    function test_PoC_dust_persists_after_claiming_streamed_amount() public {
        // Create incentive and a single LP position that will claim streamed amount
        uint256 amount = 100_000_000; // 100 USDC
        vm.prank(funder);
        gauge.createIncentive(key, IERC20(address(usdc)), amount);

        // Register one position directly via adapter-only path (adapter is this contract)
        uint256 tokenId = 1;
        bytes32 posKey = EfficientHashLib.hash(bytes32(tokenId), bytes32(PoolId.unwrap(pid)));
        gauge.notifySubscribeWithContext(tokenId, posKey, PoolId.unwrap(pid), 0, -120, 120, 1_000_000, lpOwner);

        // Advance to finish and update
        vm.warp(block.timestamp + 604800 + 1);
        gauge.pokePool(key);

        // Claim to owner via admin force-unsubscribe
        uint256 ownerBalBefore = usdc.balanceOf(lpOwner);
        gauge.adminForceUnsubscribe(posKey, true);
        uint256 ownerBalAfter = usdc.balanceOf(lpOwner);

        // Owner received streamed ~= rate * WEEK (allow 1 unit rounding difference)
        (uint256 rateAfter,,) = gauge.incentiveData(pid, IERC20(address(usdc)));
        assertEq(rateAfter, 0, "rate zero after finish");
        uint256 expectedRate = amount / 604800;
        uint256 expectedStreamed = expectedRate * 604800;
        uint256 claimed = ownerBalAfter - ownerBalBefore;
        bool withinRounding = (claimed == expectedStreamed) || (claimed + 1 == expectedStreamed);
        assertTrue(withinRounding, "owner received streamed amount within rounding tolerance");

        // Gauge retains exactly the dust (plus any unclaimed streamed, but with one LP it should be zero)
        uint256 gaugeBal = usdc.balanceOf(address(gauge));
        assertEq(gaugeBal, amount - claimed, "gauge holds unclaimed portion (dust + rounding)");
        assertGe(gaugeBal, amount - expectedStreamed, "gauge holds at least theoretical dust");
    }

    // Minimal adapter method used by adminForceUnsubscribe
    function getPoolAndPositionInfo(uint256 /*tokenId*/ ) external view returns (PoolKey memory k, PositionInfo info) {
        k = key; // return the pool key used in this test
        // info left as default zeros; not used by the code path under test
    }
}
```

## Impact

The protocol suffers a guaranteed loss of the "fractional dust" whenever incentives are created. Since rewards are streamed per second over exactly 604,800 seconds (7 days), any amount that cannot be evenly divided is truncated. For tokens with 6 decimals like USDT/USDC, this means that each second up to 0.000001 can be discarded. Over a full week, the cumulative loss can approach 0.4 USDC for every 1 USDC allocated as rewards. Tokens with fewer decimals (e.g., 4) will suffer even larger dust losses.

## Recommendation

When funding an incentive, **round the deposit down to a full-week multiple** and handle the remainder immediately so no dust can ever form:

1. Compute `effective = (amount / WEEK) * WEEK;` `remainder = amount - effective;`

2. Use `effective` to derive `rate = effective / WEEK` and start the 7-day stream.

3. **Return** `remainder` to the funder (or **carry it forward** into the next funding call via a per-pool `pendingRemainder` accumulator until it reaches at least one full `WEEK`).

This guarantees `rate * WEEK == effective` and the entire streamed budget is paid out exactly, while the remainder is never trapped as unstreamable dust.

---
id: 19607
severity: "Medium"
---

# Wrong ProfitManager in GuildToken, will always revert for other types of gauges leading to bad debt

## Description

In `GuildToken.sol`, there’s a mistake where `profitManager` is set in the constructor. This is problematic because different markets have different `ProfitManagers`, and the logic was initially designed for only one market (e.g., gUSDC). As a result, calling `notifyPnL()` with negative value (via `forgive()` or `onBid()` in other type of terms (e.g. gWETH)), it triggers `GuildToken::notifyGaugeLoss()`. However, this always results in a revert for other term types because the caller is the ProfitManager of that type, whereas `GuildToken::notifyGaugeLoss()` expects the one set in the constructor.

As a result, this means that loans from other markets won’t be removed unless users repay them, resulting in bad debt for the protocol.

[GuildToken::`notifyGaugeLoss()`](https://github.com/code-423n4/2023-12-ethereumcreditguild/blob/2376d9af792584e3d15ec9c32578daa33bb56b43/src/tokens/GuildToken.sol#L123-L129)

```solidity
function notifyGaugeLoss(address gauge) external {
    require(msg.sender == profitManager, "UNAUTHORIZED");

    // save gauge loss
    lastGaugeLoss[gauge] = block.timestamp;
    emit GaugeLoss(gauge, block.timestamp);
}
```

**Note:** It’s using this `profitManager` in other parts of `GuildToken`, but it has nothing to do with the attack, and it doesn’t cause any impact. However, we show how to fix it in the recommendation section. Because the `profitManager` should be removed altogether and always called dynamically based on the passed gauge.

## Proof of Concept

Conditions:

* 2+ market (gUSDC, gWETH, etc).
* Negative `notifyPnL()` (via `forgive()` or `onBid()`).

Firstly, you need to add additional variables for other term type and include them in the `setUp()`.

Modify `SurplusGuildMinter.t.sol` as shown:

```solidity
contract SurplusGuildMinterUnitTest is Test {
    address private governor = address(1);
    address private guardian = address(2);
    address private term;
    address private termWETH;
    Core private core;
    ProfitManager private profitManager;
    ProfitManager private profitManagerWETH;
    CreditToken credit;
    CreditToken creditWETH;
    GuildToken guild;
    RateLimitedMinter rlgm;
    SurplusGuildMinter sgm;

    // GuildMinter params
    uint256 constant MINT_RATIO = 2e18;
    uint256 constant REWARD_RATIO = 5e18;

    function setUp() public {
        vm.warp(1679067867);
        vm.roll(16848497);
        core = new Core();

        profitManager = new ProfitManager(address(core));
        profitManagerWETH = new ProfitManager(address(core));
        credit = new CreditToken(address(core), "name", "symbol");
        creditWETH = new CreditToken(address(core), "WETH", "WETH");
        guild = new GuildToken(address(core), address(profitManager));
        rlgm = new RateLimitedMinter(
            address(core), /*_core*/
            address(guild), /*_token*/
            CoreRoles.RATE_LIMITED_GUILD_MINTER, /*_role*/
            type(uint256).max, /*_maxRateLimitPerSecond*/
            type(uint128).max, /*_rateLimitPerSecond*/
            type(uint128).max /*_bufferCap*/
        );
        sgm = new SurplusGuildMinter(
            address(core),
            address(profitManager),
            address(credit),
            address(guild),
            address(rlgm),
            MINT_RATIO,
            REWARD_RATIO
        );
        profitManager.initializeReferences(address(credit), address(guild), address(0));
        profitManagerWETH.initializeReferences(address(creditWETH), address(guild), address(0));
        term = address(new MockLendingTerm(address(core)));
        termWETH = address(new MockLendingTerm(address(core)));

        // roles
        core.grantRole(CoreRoles.GOVERNOR, governor);
        core.grantRole(CoreRoles.GUARDIAN, guardian);
        core.grantRole(CoreRoles.CREDIT_MINTER, address(this));
        core.grantRole(CoreRoles.GUILD_MINTER, address(this));
        core.grantRole(CoreRoles.GAUGE_ADD, address(this));
        core.grantRole(CoreRoles.GAUGE_REMOVE, address(this));
        core.grantRole(CoreRoles.GAUGE_PARAMETERS, address(this));
        core.grantRole(CoreRoles.GUILD_MINTER, address(rlgm));
        core.grantRole(CoreRoles.RATE_LIMITED_GUILD_MINTER, address(sgm));
        core.grantRole(CoreRoles.GUILD_SURPLUS_BUFFER_WITHDRAW, address(sgm));
        core.grantRole(CoreRoles.GAUGE_PNL_NOTIFIER, address(this));
        core.grantRole(CoreRoles.GOVERNOR, address(this));

        // add gauge and vote for it
        guild.setMaxGauges(10);
        guild.addGauge(1, term);
        guild.mint(address(this), 50e18);
        guild.incrementGauge(term, uint112(50e18));

        guild.addGauge(2, termWETH);

        // labels
        vm.label(address(core), "core");
        vm.label(address(profitManager), "profitManager");
        vm.label(address(credit), "credit");
        vm.label(address(guild), "guild");
        vm.label(address(rlgm), "rlcgm");
        vm.label(address(sgm), "sgm");
        vm.label(term, "term");
    }
...
}
```

Place the test in the same `SurplusGuildMinter.t.sol` and run with:

```
forge test --match-contract "SurplusGuildMinterUnitTest" --match-test "testNotifyPnLCannotBeCalledWithNegative"
```

```solidity
function testNotifyPnLCannotBeCalledWithNegative() public {
    // Show that for the initial gUSDC term there is no problem.
    credit.mint(address(profitManager), 10);
    profitManager.notifyPnL(term, -1);

    creditWETH.mint(address(profitManagerWETH), 10);
    vm.expectRevert("UNAUTHORIZED");
    profitManagerWETH.notifyPnL(termWETH, -1);
}
```

## Recommendation

In GuildToken.sol, `ProfitManager` needs to be dynamically called, because there will be different `ProfitManager` for each market.

Since the caller of the `notifyGaugeLoss()` needs to be the `profitManager` of the passed gauge, here is the refactored logic:

```solidity
function notifyGaugeLoss(address gauge) external {
    address gaugeProfitManager = LendingTerm(gauge).getReferences().profitManager;
    require(msg.sender == gaugeProfitManager, "UNAUTHORIZED");
    require(msg.sender == profitManager, "UNAUTHORIZED");

    // save gauge loss
    lastGaugeLoss[gauge] = block.timestamp;
    emit GaugeLoss(gauge, block.timestamp);
}
```

You should also rework `_decrementGaugeWeight()` and `_incrementGaugeWeight()` as follows:

```solidity
function _decrementGaugeWeight(
    address user,
    address gauge,
    uint256 weight
) internal override {
    uint256 _lastGaugeLoss = lastGaugeLoss[gauge];
    uint256 _lastGaugeLossApplied = lastGaugeLossApplied[gauge][user];
    require(
        _lastGaugeLossApplied >= _lastGaugeLoss,
        "GuildToken: pending loss"
    );

    // update the user profit index and claim rewards
    ProfitManager(profitManager).claimGaugeRewards(user, gauge);
    address gaugeProfitManager = LendingTerm(gauge).getReferences().profitManager;
    ProfitManager(gaugeProfitManager).claimGaugeRewards(user, gauge);

    // check if gauge is currently using its allocated debt ceiling.
    // To decrement gauge weight, guild holders might have to call loans if the debt ceiling is used.
    uint256 issuance = LendingTerm(gauge).issuance();
    if (issuance != 0) {
        uint256 debtCeilingAfterDecrement = LendingTerm(gauge).debtCeiling(-int256(weight));
        require(
            issuance <= debtCeilingAfterDecrement,
            "GuildToken: debt ceiling used"
        );
    }

    super._decrementGaugeWeight(user, gauge, weight);
}

function _incrementGaugeWeight(
    address user,
    address gauge,
    uint256 weight
) internal override {
    uint256 _lastGaugeLoss = lastGaugeLoss[gauge];
    uint256 _lastGaugeLossApplied = lastGaugeLossApplied[gauge][user];
    if (getUserGaugeWeight[user][gauge] == 0) {
        lastGaugeLossApplied[gauge][user] = block.timestamp;
    } else {
        require(
            _lastGaugeLossApplied >= _lastGaugeLoss,
            "GuildToken: pending loss"
        );
    }

    ProfitManager(profitManager).claimGaugeRewards(user, gauge);
    address gaugeProfitManager = LendingTerm(gauge).getReferences().profitManager;
    ProfitManager(gaugeProfitManager).claimGaugeRewards(user, gauge);

    super._incrementGaugeWeight(user, gauge, weight);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerabilityis a mismatched ProfitManager reference in the GuildToken contract that causes the notifyGaugeLoss function to revert when the protocol operates with multiple lending markets. In the constructor the contract stores a single profitManager address, assuming a single market such as gUSDC. However, each market (for example gWETH) has its own ProfitManager. When a negative profit‑and‑loss notification is emitted for a non‑default market – for instance via the forgive or onBid functions – the GuildToken contract calls notifyGaugeLoss. This function checks that msg.sender equals the profitManager stored at deployment. Because the caller is the ProfitManager of the specific market, the check fails and the transaction reverts with an UNAUTHORIZED error. The revert prevents the protocol from recording the gauge loss and from removing the associated loan, so the debt remains on the books as bad debt. The issue manifests only when a negative PnL occurs in a market other than the one hard‑coded in the constructor, making it easy to miss during normal positive‑PnL testing. It affects the protocol’s accounting integrity, borrowers who cannot close their positions, lenders who see un‑recoverable exposure, and token holders whose balances may not reflect the true state of the system. The bug was discovered during a Code4rena audit that examined the interaction between GuildToken and multiple LendingTerm contracts. It is hard to notice because the contract works correctly for the default market and the failure only appears under specific loss‑making scenarios. To fix the issue the contract should no longer store a static profitManager; instead it must retrieve the appropriate ProfitManager dynamically from the LendingTerm associated with the gauge being notified, and adjust internal weight‑handling functions to reference the correct manager. This change restores proper authorization checks, allows gauge losses to be recorded for any market, and prevents the accumulation of unrecoverable debt.

---
id: 4969
severity: "High"
---

# Rewards/Fees claimed by LPers are not removed from the market Submitted by Honour

## Description

In TermMax when an LPer withdraws liquidity (i.e. convert their lp tokens lpFt/lpXt
to ft/xt) , the LPer receives additional ft/xt proportional to the reward accrued by their share of lpFt/lpXt.
```solidity
function _withdrawLiquidity(
address caller,
uint256 lpFtAmt,
uint256 lpXtAmt
) internal returns (uint128 ftOutAmt, uint128 xtOutAmt) {
MarketConfig memory mConfig = _config;
// calculate out put amount
uint ftReserve = ft.balanceOf(address(this));
if (lpFtAmt > 0) {
ftOutAmt = TermMaxCurve
.calculateLpWithReward( // <<<
lpFtAmt,
lpFt.totalSupply(),
lpFt.balanceOf(address(this)),
ftReserve,
block.timestamp,
mConfig
)
.toUint128();
lpFt.transferFrom(caller, address(this), lpFtAmt);
lpFt.burn(lpFtAmt);
}
uint xtReserve = xt.balanceOf(address(this));
if (lpXtAmt > 0) {
xtOutAmt = TermMaxCurve
.calculateLpWithReward( // <<<
lpXtAmt,
lpXt.totalSupply(),
lpXt.balanceOf(address(this)),
xtReserve,
block.timestamp,
mConfig
)
.toUint128();
lpXt.transferFrom(caller, address(this), lpXtAmt);
lpXt.burn(lpXtAmt);
}
//...SNIP...
}
function calculateLpWithReward(
uint256 lpAmt,
uint256 lpTotalSupply,
uint256 lpReserve,
uint256 tokenReserve,
uint256 currentTime,
MarketConfig memory config
) internal pure returns (uint256 tokenAmt) {
uint reward = calculateLpReward(
currentTime,
config.openTime,
config.maturity,
lpTotalSupply,
lpAmt,
lpReserve
);
lpAmt += reward;
tokenAmt = (lpAmt * tokenReserve) / lpTotalSupply;
}
```
The rewards calculations can be seen in the docs, the most notable equation is.
Rewardlp = Rewarddistributed ×
lpAmt
lpSupply −Rewardtotal
The issue is that the user's lpAmt is burned but their Rewardlp claimed is not burned, meaning the total
rewards to distribute remains the same after user claim their rewards. For a simple example , assuming:
• lpSupply = 100
• Rewardtotal = 20
• Rewarddistributed = 10
suppose Alice and Bob are LPers with lpAmt = 40 and lpAmt = 40 respectively.
Alice's Rewardlp = $ 10 \times \frac{40}{100 - 20} = 5$.
When alice withdraws her lpAmt is burned so lpSupply = 100 −40 = 60 but her Rewardlp is not burned so
Rewarddistributed remains 10.
Now when Bob withdraws his Rewardlp = 10 ×
60−20 = 10.
The market has paid a total of 15lp in rewards when only 10 was available for distribution. Bob received
twice the amount of rewards when both LPers had equal lp's in the market.

Impact Explanation:
High - incorrect rewards distribution, in worst case as Rewarddistributed reaches
Rewardtotal ,total lp paid can exceed Rewardtotal leading to loss of funds for other LPers.

## Proof of Concept

Add test to test/Configuration.t.sol and run:
forge test --mt testRewardDistribution -vvv
```solidity
function testRewardDistribution() public {
address alice = makeAddr("alice");
address bob = makeAddr("bob");
address charlie = makeAddr("charlie");
res.underlying.mint(alice, 100e8);
res.underlying.mint(bob, 100e8);
res.underlying.mint(charlie, 100e8);
//1. Alice, Bob and Charlie provide liquidity
vm.startPrank(alice);
res.underlying.approve(address(res.market), type(uint256).max);
res.market.provideLiquidity(100e8);
vm.stopPrank();
vm.startPrank(bob);
res.underlying.approve(address(res.market), type(uint256).max);
res.market.provideLiquidity(100e8);
vm.stopPrank();
vm.startPrank(charlie);
res.underlying.approve(address(res.market), type(uint256).max);
res.market.provideLiquidity(100e8);
vm.stopPrank();
console.log(
"rewards before trades lpFt: %d lpXt: %d",
res.lpFt.balanceOf(address(res.market)),
res.lpXt.balanceOf(address(res.market))
);
// fees are generated when users buy or sell tokens
simulateTradesToAccrueFees();
console.log(
"rewards after trades lpFt: %d lpXt: %d",
res.lpFt.balanceOf(address(res.market)),
res.lpXt.balanceOf(address(res.market))
);
//Just to increase unlocked rewards
vm.warp(block.timestamp + 40 days); //21 days left to maturity
//2. Alice, Bob and Charlie withdraw liquidity
vm.startPrank(alice);
res.lpFt.approve(address(res.market), type(uint256).max);
res.lpXt.approve(address(res.market), type(uint256).max);
(uint256 ftOut, uint256 xtOut) =
res.market.withdrawLiquidity(uint128(res.lpFt.balanceOf(alice)), uint128(res.lpXt.balanceOf(alice)));
res.ft.approve(address(res.market), type(uint256).max);
res.xt.approve(address(res.market), type(uint256).max);
uint redeemAmt = ftOut * 1e8 / res.marketConfig.initialLtv;
redeemAmt = redeemAmt < xtOut ? redeemAmt : xtOut;
res.market.redeemFtAndXtToUnderlying(uint128(redeemAmt));
vm.stopPrank();
vm.startPrank(bob);
res.lpFt.approve(address(res.market), type(uint256).max);
res.lpXt.approve(address(res.market), type(uint256).max);
(ftOut, xtOut) =
res.market.withdrawLiquidity(uint128(res.lpFt.balanceOf(bob)), uint128(res.lpXt.balanceOf(bob)));
res.ft.approve(address(res.market), type(uint256).max);
res.xt.approve(address(res.market), type(uint256).max);
redeemAmt = ftOut * 1e8 / res.marketConfig.initialLtv;
redeemAmt = redeemAmt < xtOut ? redeemAmt : xtOut;
res.market.redeemFtAndXtToUnderlying(uint128(redeemAmt));
vm.stopPrank();
vm.startPrank(charlie);
res.lpFt.approve(address(res.market), type(uint256).max);
res.lpXt.approve(address(res.market), type(uint256).max);
(ftOut, xtOut) =
res.market.withdrawLiquidity(uint128(res.lpFt.balanceOf(charlie)),
uint128(res.lpXt.balanceOf(charlie)));
res.ft.approve(address(res.market), type(uint256).max);
res.xt.approve(address(res.market), type(uint256).max);
redeemAmt = ftOut * 1e8 / res.marketConfig.initialLtv;
redeemAmt = redeemAmt < xtOut ? redeemAmt : xtOut;
res.market.redeemFtAndXtToUnderlying(uint128(redeemAmt));
vm.stopPrank();
console.log(
"rewards after withdraws lpFt: %d lpXt: %d",
res.lpFt.balanceOf(address(res.market)),
res.lpXt.balanceOf(address(res.market))
);
console.log(
"alice's balance: %d
bob's balance: %d charlie's balance: %d",
res.underlying.balanceOf(alice),
res.underlying.balanceOf(bob),
res.underlying.balanceOf(charlie)
);
}
function simulateTradesToAccrueFees() internal {
for (uint256 i; i < 30; i++) {
address trader = vm.randomAddress();
res.underlying.mint(trader, 50e8);
vm.startPrank(trader);
res.underlying.approve(address(res.market), type(uint256).max);
uint256 tokenOut = res.market.buyFt(50e8, 0);
res.ft.approve(address(res.market), type(uint256).max);
uint256 underlyingOut = res.market.sellFt(uint128(tokenOut), 0);
tokenOut = res.market.buyXt(uint128(underlyingOut), 0);
res.xt.approve(address(res.market), type(uint256).max);
underlyingOut = res.market.sellXt(uint128(tokenOut), 0);
vm.stopPrank();
}
}
```
Output:
Logs:
rewards before trades lpFt: 0 lpXt: 0
rewards after trades lpFt: 900469856 lpXt: 3570719028
rewards after withdraws lpFt: 900469856 lpXt: 3570719028
alice's balance: 10186267310
bob's balance: 10206021838 charlie's balance: 10305647923
As we see rewards remains the same even after all LPers withdraw liquidity from the market and rewards
distributed to each Lper is different even though they withdraw equal amounts of liquidity.

## Recommendation

Burn the reward lp claimed as well.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an accounting error in the liquidity withdrawal path of the TermMax market where the reward portion of a liquidity provider's claim is not removed from the contract state. When a provider calls withdrawLiquidity the contract calculates the total token amount to return by adding a reward term to the amount of LP tokens being burned. The LP tokens representing the provider's share are correctly transferred and burned, but the extra reward tokens that were added to the calculation remain in the contract and are never burned or deducted from the reward pool. Because the reward pool balance (Rewarddistributed) is not decreased, subsequent withdrawals are performed against a smaller effective LP supply while the same reward pool is still considered available, causing later providers to receive a larger share of the rewards than they are entitled to. This can be exploited by any LP who withdraws after fees have accrued: the first withdrawer receives the correct reward, but the contract’s internal accounting still reports the full reward amount as undistributed, so the next withdrawer receives an inflated reward, and so on. In the worst case the total rewards paid out can exceed the total rewards that were ever generated, draining funds that should belong to other liquidity providers. The bug manifests only when withdrawals happen after the market has generated fees and accrued rewards; it does not appear during normal trading or when no rewards are claimed. All liquidity providers, the protocol’s reward pool, and any downstream users of the market are affected because the over‑distribution reduces the overall pool of assets and can lead to loss of value for later participants. The issue was discovered during a formal audit when a test that simulated multiple providers withdrawing after fee accrual showed that the reward token balances of the market contract remained unchanged even though LP tokens were burned, and that providers with equal shares received different reward amounts. The problem is subtle because the contract’s external view of reward balances may look correct at a glance, while the internal accounting of total supply is inconsistent, making the bug easy to miss without detailed state inspection. The proper fix is to treat the reward portion as part of the LP token that is being burned – i.e., to also burn the reward amount or otherwise reduce the Rewarddistributed counter when a provider claims rewards – ensuring that the total reward pool is accurately decremented and that future withdrawals are calculated against the correct remaining reward balance. This class of bug falls under reward double‑spend or improper state update after reward claim, violating the protocol’s accounting assumptions that total rewards distributed never exceed the amount generated.

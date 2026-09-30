---
id: 4963
severity: "High"
---

# Malicious users can steal swap fees from liquidity providers Submitted by 0x37, also found by Roberto, newspacexyz, davidjohn241018 and Honour

## Description

In swap process, some swap fees will be generated and these swap fees are in term of lp tokens. When LP holders want to remove liquidity, they will get some reward according to the fee distribution.
We have one design that LPs can get more rewards if they hold Lp longer. The problem is that even if these liquidity is deposited in this transaction, this LP can still get some rewards via removing liquidity:
```solidity
function calculateLpReward(
    uint256 currentTime,
    uint256 openMarketTime,
    uint256 maturity,
    uint256 lpSupply,
    uint256 lpAmt,
    uint256 totalReward
) internal pure returns (uint256 reward) {
    uint t = (lpSupply - totalReward) * (2 * maturity - openMarketTime - currentTime);
    reward = ((totalReward * lpAmt) * (currentTime - openMarketTime)) / t;
}
```

Impact Explanation:
Malicious users can steal rewards via flashloan. The normal LP will lose some rewards.

## Proof of Concept

Add this test case into TermMaxRouter.t.sol. In this case, Alice is the malicious user, and the deployer is the normal LP. If Alice doesn't add/remove liquidity in this test case, the output is like as below:
ft amount received in deployer:
880738388498
xt amount received in deployer:
1000821070844
If Alice adds and removes liquidity before Deployer's remove, the output is like as below:
ft amount received in deployer:
880036223746
xt amount received in deployer:
999548671891
Compared these two results, the normal user Deployer will lose some rewards.
```solidity
function testPocReward() public {
    vm.startPrank(deployer);
    res.underlying.approve(address(res.market), 2000e8);
    // Trade some Ft, Xt to generate some swap fees.
    res.market.buyFt(1000e8, 0);
    res.market.buyXt(1000e8, 0);
    res.ft.approve(address(res.market), res.ft.balanceOf(deployer));
    res.xt.approve(address(res.market), res.xt.balanceOf(deployer));
    res.market.sellFt(uint128(res.ft.balanceOf(deployer)), 0);
    res.market.sellXt(uint128(res.xt.balanceOf(deployer)), 0);
    vm.stopPrank();
    console.log("maturity: ", res.marketConfig.maturity);
    console.log("current block.timestamp: ", block.timestamp);
    vm.warp(block.timestamp + 57 days);
    console.log("current block.timestamp reaches the maturiy: ", block.timestamp);
    vm.startPrank(alice);
    res.underlying.approve(address(res.market), 100000e8);
    res.market.provideLiquidity(100000e8);
    res.lpFt.approve(address(router), res.lpFt.balanceOf(alice));
    res.lpXt.approve(address(router), res.lpXt.balanceOf(alice));
    router.withdrawLiquidityToFtXt(alice, res.market, res.lpFt.balanceOf(alice), res.lpXt.balanceOf(alice), 0, 0);
    res.underlying.approve(address(res.market), 100000e8);
    res.market.provideLiquidity(100000e8);
    res.lpFt.approve(address(router), res.lpFt.balanceOf(alice));
    res.lpXt.approve(address(router), res.lpXt.balanceOf(alice));
    router.withdrawLiquidityToFtXt(alice, res.market, res.lpFt.balanceOf(alice), res.lpXt.balanceOf(alice), 0, 0);
    console.log("Alice ft received amount: ", res.ft.balanceOf(alice));
    console.log("Alice xt received amount: ", res.xt.balanceOf(alice));
    vm.stopPrank();
    vm.startPrank(deployer);
    res.lpFt.approve(address(router), res.lpFt.balanceOf(deployer));
    res.lpXt.approve(address(router), res.lpXt.balanceOf(deployer));
    router.withdrawLiquidityToFtXt(deployer, res.market, res.lpFt.balanceOf(deployer) - 1, res.lpXt.balanceOf(deployer) - 1, 0, 0);
    console.log("ft amount received in deployer: ", res.ft.balanceOf(deployer));
    console.log("xt amount received in deployer: ", res.xt.balanceOf(deployer));
    res.ft.transfer(address(res.market), res.ft.balanceOf(deployer));
    res.xt.transfer(address(res.market), res.xt.balanceOf(deployer));
    vm.stopPrank();
}
```

## Recommendation

We should consider the liquidity's actual active time in this pool when we calculate these liquidity's rewards.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability lies in the reward‑distribution logic of the liquidity pool, where the amount of swap fees allocated to each liquidity provider (LP) is calculated without taking into account the actual time that the LP’s capital has been active in the pool. The formula uses the current block timestamp, the market opening time and the maturity date, but it only multiplies the LP’s token amount by the elapsed time since the market opened, ignoring whether the LP has been present for that whole interval. As a result, a malicious actor can deposit liquidity and withdraw it in the same transaction – for example by using a flash‑loan – and still receive a share of the accumulated fees that should belong to longer‑standing LPs. The attacker’s reward is derived from the same proportional calculation that rewards honest LPs, so the protocol mistakenly credits the attacker even though the capital was only present for an instant. This exploit reduces the amount of tokens that honest LPs receive when they later remove their liquidity; they observe lower balances than expected, effectively seeing part of their accrued fees disappear. The issue manifests whenever swap fees have been generated and a user is allowed to add and then immediately remove liquidity before other LPs perform their withdrawals, which can be done within a single block. All liquidity providers are affected because the incentive model is broken and the protocol’s accounting assumptions – that rewards are earned proportionally to time held – are violated. The problem was uncovered during a security audit by Spearbit, where a test case demonstrated that a malicious user (named Alice) could add and withdraw liquidity twice before a normal LP (the deployer) removed theirs, resulting in a measurable loss of rewards for the honest LP. The bug is subtle because the reward numbers still follow the intended formula, making the loss appear as a normal variance rather than a clear error, and because the contract does not record per‑LP timestamps to enforce a minimum holding period. To remediate the issue, the reward calculation should be based on each LP’s actual active duration, for example by storing the deposit timestamp for every position and weighting the fee share by the time the capital has been locked, or by preventing immediate withdrawal after a deposit. This change would align the distribution with the intended economic model and stop attackers from siphoning fees through flash‑loan‑style attacks.

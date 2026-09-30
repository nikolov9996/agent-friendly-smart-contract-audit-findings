---
id: 19090
severity: "High"
---

# `AaveStrategy.sol`: Changing swapper breaks the contract

## Description

The contract `AaveStrategy.sol` manages wETH tokens and deposits them to the aave lending pool, and collects rewards. These rewards are then swapped into WETH again to compound on the WETH being managed by the contract. this is done in the `compound` function.

```solidity
uint256 calcAmount = swapper.getOutputAmount(swapData, "");
uint256 minAmount = calcAmount - (calcAmount * 50) / 10_000; //0.5%
swapper.swap(swapData, minAmount, address(this), "");
```

To carry out these operations, the swapper contract needs to be given approval to use the tokens being stored in the strategy contract. This is required since the swapper contract calls transferFrom on the tokens to pull it out of the strategy contract. This allowance is set in the constructor.

```solidity
rewardToken.approve(_multiSwapper, type(uint256).max);
```

The issue arises when the swapper contract is changed. The change is done via the `setMultiSwapper` function. This function however does not give approval to the new swapper contract. Thus if the swapper is upgraded/changed, the approval is not transferred to the new swapper contract, which makes the swappers dysfunctional.

Since the swapper is critical to the system, and `compound` is called before withdrawals, a broken swapper will break the withdraw functionality of the contract. Thus this is classified as a high severity issue.

## Proof of Concept

The bug is due to the absence of `approve` calls in the `setMultiSwapper` function. This can be seen from the implementation of the function.

```solidity
function setMultiSwapper(address _swapper) external onlyOwner {
    emit MultiSwapper(address(swapper), _swapper);
    swapper = ISwapper(_swapper);
}
```

## Recommendation

In the `setMultiSwapper` function, remove approval from the old swapper and add approval to the new swapper. The same function has the proper implementation in the `ConvexTricryptoStrategy.sol` contract which can be used here as well.

```solidity
function setMultiSwapper(address _swapper) external onlyOwner {
    emit MultiSwapper(address(swapper), _swapper);
    rewardToken.approve(address(swapper), 0);
    swapper = ISwapper(_swapper);
    rewardToken.approve(_swapper, type(uint256).max);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is that the strategy contract grants an unlimited ERC20 allowance to a swapper contract only at deployment, and when the owner later updates the swapper address via setMultiSwapper, the contract does not revoke the old allowance nor grant a new allowance to the replacement. As a result the new swapper cannot call transferFrom on the reward token, causing the swap step in the compound function to revert or return zero. Because compound is executed before any user withdrawal, a broken swapper prevents the contract from converting rewards back to WETH, which in turn blocks withdrawals and may leave user balances appearing unchanged or zero. The issue occurs whenever the owner calls setMultiSwapper, which is intended for upgrading or fixing the swapper logic. It affects all users of the strategy, the protocol that relies on the compounded returns, and any funds held in the contract. The bug was discovered during a manual audit that compared the implementation of setMultiSwapper with a similar function in another strategy where the allowance handling was correct. The problem is subtle because the contract still holds a valid allowance for the old address, so the missing approval for the new address does not raise an immediate error until a swap is attempted. The class of bug is an “missing token allowance reset on contract address change”, a common pattern when ERC20 approvals are tied to mutable external contracts. Exploitation does not require a malicious actor; simply updating the swapper to a new contract (or an attacker forcing such an update) will render the swap functionality inoperable, leading to failed reward conversion and blocked withdrawals. From a user perspective the UI may show a successful withdrawal request but the transaction reverts, or the user sees no change in their displayed balance after a withdrawal attempt. The expected behavior is that rewards are swapped and users can withdraw their share, but the reality is that the swap fails and funds remain locked. The fix is to modify setMultiSwapper so that it first revokes the allowance from the previous swapper (by approving zero) and then grants an unlimited allowance to the new swapper, mirroring the pattern used in the ConvexTricryptoStrategy contract.

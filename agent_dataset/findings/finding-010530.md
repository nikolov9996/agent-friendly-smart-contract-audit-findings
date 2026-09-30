---
id: 10530
severity: "High"
---

# Bonding token transfers DOS after the pair was created

## Description

Users are not permitted to transfer bonding tokens before the initial sale is concluded and the Token/WETH pair is created:
```solidity
function _update(address from, address to, uint256 value) internal virtual override {
    // will revert for normal transfer till goal not reached
    if (
        !liquidityGoalReached() && from != address(0) && to != address(0) && from != address(this)
        && to != address(this)
    ) revert TransferNotAllowedUntilLiquidityGoalReached();
    super._update(from, to, value);
}
```
Unfortunately, this protection can be exploited to perform DoS on token transfers after the pair with initial liquidity has been created. An attacker can donate MAX_TOTAL_SUPPLY - availableTokenBalance + 1 tokens and reset the liquidityGoalReached():
```solidity
function liquidityGoalReached() public view returns (bool) {
    return getReserve() <= (MAX_TOTAL_SUPPLY - availableTokenBalance);
}
```
Coded POC for the ContinuosBondingERC20TokenTest.t.sol:
```solidity
function testTokenDown() public {
    vm.deal(user, 10_000 ether);
    vm.startPrank(user);
    bondingERC20Token.buyTokens{ value: 202.2 ether }(0);
    vm.expectRevert();
    bondingERC20Token.buyTokens{ value: 1 wei }(0);
    // pair is created
    assertEq(bondingERC20Token.isLpCreated(), true);
    assertEq(bondingERC20Token.getReserve(), 0);
    // donate tokens to the ERC20 contract
    bondingERC20Token.transfer(address(bondingERC20Token), 200_000_001 ether);
    // revert TransferNotAllowedUntilLiquidityGoalReached()
    vm.expectRevert();
    bondingERC20Token.transfer(address(this), 10 ether);
}
```

## Proof of Concept

No poc.

## Recommendation

```solidity
function _update(address from, address to, uint256 value) internal virtual override {
    // will revert for normal transfer till goal not reached
    if (
        !liquidityGoalReached() && from != address(0) && to != address(0) && from != address(this)
        && to != address(this) && !isPairCreated
    ) revert TransferNotAllowedUntilLiquidityGoalReached();
    super._update(from, to, value);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The contract implements a bonding ERC‑20 token that blocks all normal transfers until a liquidity goal is reached. The blocking logic lives in the overridden _update function, which reverts with TransferNotAllowedUntilLiquidityGoalReached when the liquidityGoalReached() view returns false and the transfer is not a mint or burn. The liquidityGoalReached() function determines success by comparing the current reserve of the token/WETH pair (getReserve()) with the difference between the maximum token supply and the amount of tokens still available for purchase (MAX_TOTAL_SUPPLY‑availableTokenBalance). After the initial sale finishes, the pair is created, getReserve() becomes zero and the condition evaluates to true, so transfers are allowed. However, the check does not also verify that the pair has already been created. An attacker can exploit this by sending a large amount of tokens directly to the token contract itself, which reduces availableTokenBalance. This manipulation makes the expression (MAX_TOTAL_SUPPLY‑availableTokenBalance) grow, causing liquidityGoalReached() to flip back to false even though the pair already exists. Because the _update guard no longer distinguishes the post‑creation state, every subsequent transfer – including legitimate user transfers or contract‑initiated moves – triggers the revert, effectively creating a denial‑of‑service condition on token movement. From a user’s perspective the token appears frozen: attempts to send tokens result in a transaction that reverts with TransferNotAllowedUntilLiquidityGoalReached, balances remain unchanged, and no funds can be transferred out of the contract. The impact is severe because token holders lose the ability to move or trade their assets, and the protocol’s liquidity mechanisms become unusable. The issue was discovered during a security audit when a test case deliberately transferred MAX_TOTAL_SUPPLY‑availableTokenBalance+1 tokens to the token contract and observed that further transfers reverted. The bug is subtle because the original intention of the guard – to prevent transfers before the sale ends – is correct; the missing isLpCreated guard makes the condition unintentionally re‑activate after the pair is created, a scenario that is not obvious during casual testing. The proper fix is to augment the transfer restriction with an explicit check that the liquidity pair has already been created (e.g., && !isLpCreated) so that once the pair exists the transfer guard is disabled regardless of the liquidityGoalReached() result. This change restores normal token transfer functionality while preserving the intended pre‑sale protection, and eliminates the DoS vector caused by manipulating the available token balance.

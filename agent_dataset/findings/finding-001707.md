---
id: 1707
severity: "High"
---

# `LiquidityProviders.sol` The share price of the LP can be manipulated and making future liquidityProviders unable to `removeLiquidity

## Description

```solidity
function removeLiquidity(uint256 _nftId, uint256 _amount)
    external
    nonReentrant
    onlyValidLpToken(_nftId, _msgSender())
    whenNotPaused
{
    (address _tokenAddress, uint256 nftSuppliedLiquidity, uint256 totalNFTShares) = lpToken.tokenMetadata(_nftId);
    require(_isSupportedToken(_tokenAddress), "ERR__TOKEN_NOT_SUPPORTED");

    require(_amount != 0, "ERR__INVALID_AMOUNT");
    require(nftSuppliedLiquidity >= _amount, "ERR__INSUFFICIENT_LIQUIDITY");
    whiteListPeriodManager.beforeLiquidityRemoval(_msgSender(), _tokenAddress, _amount);
    // Claculate how much shares represent input amount
    uint256 lpSharesForInputAmount = _amount * getTokenPriceInLPShares(_tokenAddress);

    // Calculate rewards accumulated
    uint256 eligibleLiquidity = sharesToTokenAmount(totalNFTShares, _tokenAddress);
```

```solidity
function sharesToTokenAmount(uint256 _shares, address _tokenAddress) public view returns (uint256) {
    return (_shares * totalReserve[_tokenAddress]) / totalSharesMinted[_tokenAddress];
}
```
The share price of the liquidity can be manipulated to an extremely low value (1 underlying token worth a huge amount of shares), making it possible for `sharesToTokenAmount(totalNFTShares, _tokenAddress)` to overflow in `removeLiquidity()` and therefore freeze users’ funds.

## Proof of Concept

1. Alice `addTokenLiquidity()` with `1e8 * 1e18` XYZ on B-Chain, totalSharesMinted == `1e44`;
2. Alice `sendFundsToUser()` and bridge `1e8 * 1e18` XYZ from B-Chain to A-Chain;
3. Alice `depositErc20()` and bridge `1e8 * 1e18` XYZ from A-Chain to B-Chain;
4. Alice `removeLiquidity()` and withdraw `1e8 * 1e18 - 1` XYZ, then: `totalReserve` == `1 wei` XYZ, and `totalSharesMinted` == `1e26`;
5. Bob `addTokenLiquidity()` with `3.4e7 * 1e18` XYZ;
6. Bob tries to `removeLiquidity()`.

Expected Results: Bob to get back the deposits;

Actual Results: The tx reverted due to overflow at `sharesToTokenAmount()`.

## Recommendation

```solidity
function _increaseLiquidity(uint256 _nftId, uint256 _amount) internal onlyValidLpToken(_nftId, _msgSender()) {
    (address token, uint256 totalSuppliedLiquidity, uint256 totalShares) = lpToken.tokenMetadata(_nftId);

    require(_amount > 0, "ERR__AMOUNT_IS_0");
    whiteListPeriodManager.beforeLiquidityAddition(_msgSender(), token, _amount);

    uint256 mintedSharesAmount;
    // Adding liquidity in the pool for the first time
    if (totalReserve[token] == 0) {
        mintedSharesAmount = BASE_DIVISOR * _amount;
    } else {
        mintedSharesAmount = (_amount * totalSharesMinted[token]) / totalReserve[token];
    }
    ...
```
Consider locking part of the first mint’s liquidity to maintain a minimum amount of `totalReserve[token]`, so that the share price can not be easily manipulated.

Great find, with a PoC, deserves a severity of high because it is a valid attack path that does not have hand-wavy hypotheticals.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the liquidity‑removal routine of the LP contract, where the conversion from LP shares back to the underlying token is performed by the function sharesToTokenAmount. This function calculates the token amount as (_shares * totalReserve) / totalSharesMinted. Because the contract does not protect the multiplication step, an attacker can manipulate the internal pricing by first supplying an extremely large amount of liquidity, which inflates totalSharesMinted, and then withdrawing almost all of the underlying token, leaving the pool with a tiny reserve (as little as one wei) while totalSharesMinted remains huge. When a subsequent user calls removeLiquidity, the contract multiplies the user’s share balance (which can still be very large) by the now‑tiny totalReserve. The product exceeds the 256‑bit limit, causing an arithmetic overflow. The overflow triggers a revert inside removeLiquidity, preventing the conversion and effectively freezing the user’s funds in the pool. From a user’s perspective, the transaction fails with an out‑of‑gas or overflow error, the expected token refund never arrives, and the balance displayed in the UI remains unchanged, creating confusion and a perception that the funds have disappeared. The issue is a classic case of unchecked arithmetic combined with a manipulable price‑oracle‑like relationship between reserve and share count. It was identified during a formal audit when a proof‑of‑concept reproduced the overflow by having Alice add a massive amount of XYZ tokens, withdraw almost all of it, and then observe that Bob’s attempt to remove liquidity reverted. The bug is subtle because normal operations with balanced reserves do not trigger the overflow, making it easy to overlook during testing. To remediate, the contract should enforce a minimum reserve after any withdrawal, lock a portion of the initial liquidity to keep totalReserve from collapsing, and/or rewrite the conversion formula to perform division before multiplication or include safe‑math checks that detect potential overflow before it occurs. By ensuring the reserve cannot be reduced below a safe threshold, the share price cannot be driven to an extreme low value, eliminating the overflow path and restoring the ability of all liquidity providers to withdraw their funds safely.

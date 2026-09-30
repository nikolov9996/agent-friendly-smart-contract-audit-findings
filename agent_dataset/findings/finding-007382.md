---
id: 7382
severity: "High"
---

# First depositor can break minting of shares

## Description

The attack vector and impact is the same as [TOB-YEARN-003](https://github.com/yearn/yearn-security/blob/master/audits/20210719_ToB_yearn_vaultsv2/ToB_-_Yearn_Vault_v_2_Smart_Contracts_Audit_Report.pdf), where users may not receive shares in exchange for their deposits if the total asset amount has been manipulated through a large “donation”.

## Proof of Concept

In `BathToken.sol:569-571`, the allocation of shares is calculated as follows:

```solidity
(totalSupply == 0) ? shares = assets : shares = (
    assets.mul(totalSupply)
).div(_pool);
```

An early attacker can exploit this by:

* Attacker calls `openBathTokenSpawnAndSignal()` with `initialLiquidityNew = 1`, creating a new bath token with `totalSupply = 1`
* Attacker transfers a large amount of underlying tokens to the bath token contract, such as `1000000`
* Using `deposit()`, a victim deposits an amount less than `1000000`, such as `1000`:

  * `assets = 1000`
  * `(assets * totalSupply) / _pool = (1000 * 1) / 1000000 = 0.001`, which would round down to `0`
  * Thus, the victim receives no shares in return for his deposit

To avoid minting 0 shares, subsequent depositors have to deposit equal to or more than the amount transferred by the attacker. Otherwise, their deposits accrue to the attacker who holds the only share.

```solidity
it("Victim receives 0 shares", async () => {
    // 1. Attacker deposits 1 testCoin first when creating the liquidity pool
    const initialLiquidityNew = 1;
    const initialLiquidityExistingBathToken = ethers.utils.parseUnits("100", decimals);
    
    // Approve DAI and testCoin for bathHouseInstance
    await testCoin.approve(bathHouseInstance.address, initialLiquidityNew, {
        from: attacker,
    });
    await DAIInstance.approve(
        bathHouseInstance.address,
        initialLiquidityExistingBathToken,
        { from: attacker }
    );

    // Call open creation function, attacker deposits only 1 testCoin
    const desiredPairedAsset = await DAIInstance.address;
    await bathHouseInstance.openBathTokenSpawnAndSignal(
        await testCoin.address,
        initialLiquidityNew,
        desiredPairedAsset,
        initialLiquidityExistingBathToken,
        { from: attacker }
    );
    
    // Retrieve resulting bathToken address
    const newbathTokenAddress = await bathHouseInstance.getBathTokenfromAsset(testCoin.address);
    const _newBathToken = await BathToken.at(newbathTokenAddress);

    // 2. Attacker deposits large amount of testCoin into liquidity pool
    let attackerAmt = ethers.utils.parseUnits("1000000", decimals);
    await testCoin.approve(newbathTokenAddress, attackerAmt, {from: attacker});
    await testCoin.transfer(newbathTokenAddress, attackerAmt, {from: attacker});

    // 3. Victim deposits a smaller amount of testCoin, receives 0 shares
    // In this case, we use (1 million - 1) testCoin
    let victimAmt = ethers.utils.parseUnits("999999", decimals);
    await testCoin.approve(newbathTokenAddress, victimAmt, {from: victim});
    await _newBathToken.deposit(victimAmt, victim, {from: victim});
    
    assert.equal(await _newBathToken.balanceOf(victim), 0);
});
```

## Recommendation

* [Uniswap V2 solved this problem by sending the first 1000 LP tokens to the zero address](https://github.com/Uniswap/v2-core/blob/master/contracts/UniswapV2Pair.sol#L119-L124). The same can be done in this case i.e. when `totalSupply() == 0`, send the first min liquidity LP tokens to the zero address to enable share dilution.
  * In `_deposit()`, ensure the number of shares to be minted is non-zero:

```solidity
require(shares != 0, "No shares minted");
```

Great issue, what do y’all think of this code snippet as a solution:

```solidity
/// @notice Deposit assets for the user and mint Bath Token shares to receiver
function _deposit(uint256 assets, address receiver) internal returns (uint256 shares) {
    uint256 _pool = underlyingBalance();
    uint256 _before = underlyingToken.balanceOf(address(this));
    
    // **Assume caller is depositor**
    underlyingToken.safeTransferFrom(msg.sender, address(this), assets);
    uint256 _after = underlyingToken.balanceOf(address(this));
    assets = _after.sub(_before); // Additional check for deflationary tokens

    if (totalSupply == 0) {
        uint minLiquidityShare = 10**3;
        shares = assets.sub(minLiquidityShare);
        // Handle protecting from an initial supply spoof attack
        _mint(address(0), (minLiquidityShare));
    } else {
        shares = (assets.mul(totalSupply)).div(_pool);
    }

    // Send shares to designated target
    _mint(receiver, shares);

    require(shares != 0, "No shares minted");
    emit LogDeposit(
        assets,
        underlyingToken,
        shares,
        msg.sender,
        underlyingBalance(),
        outstandingAmount,
        totalSupply
    );
    emit Deposit(msg.sender, msg.sender, assets, shares);
}
```

LGTM :P

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a share‑minting edge case that allows an attacker to manipulate the accounting of a Bath Token pool so that later depositors receive zero shares for their deposited assets. The contract calculates the number of shares to mint based on whether the total supply of shares is zero; if it is not, the formula shares = assets × totalSupply / _pool is used. An attacker can create a pool with a non‑zero total supply (for example by initializing the token with a single share) and then transfer a very large amount of the underlying asset into the pool before any legitimate user deposits. Because the pool’s underlying balance (_pool) is now artificially inflated, the division in the share formula rounds down to zero for any subsequent deposit that is smaller than the attacker’s donation. The contract does not revert when zero shares are minted, so the victim’s transaction succeeds but the user’s balance of Bath Token shares remains at zero. From the user’s point of view the UI shows that the deposit was accepted, yet no receipt tokens appear and the underlying tokens are effectively lost, violating the expectation that a deposit yields a proportional share of the pool.

The root cause is the reliance on a simple proportional formula without a safeguard against a zero‑share result when totalSupply is already non‑zero and the pool balance has been inflated. The logic only treats the special case of totalSupply == 0, assuming that the first depositor will always receive a non‑zero amount of shares. By allowing the attacker to seed the pool with a minimal share count and then donate a large amount of assets, the invariant that assets × totalSupply / _pool > 0 is broken. This creates a situation where the accounting for share issuance no longer reflects the true value of deposited assets.

Exploitation proceeds in three steps: (1) the attacker creates a new Bath Token contract and ensures that totalSupply is set to a minimal non‑zero value; (2) the attacker transfers a large amount of the underlying token directly into the contract, inflating the pool balance without minting additional shares; (3) a victim deposits a normal‑sized amount, which the contract values against the inflated pool, resulting in a calculated share amount that rounds down to zero. The victim’s assets remain locked in the contract, while the attacker holds the only share and can later withdraw the entire pool balance, effectively stealing the victims’ funds. The attack works whenever the pool balance can be externally increased between the initialization of totalSupply and the first legitimate deposit, and when the deposit amount is not large enough to overcome the rounding effect.

The issue was identified during a code audit that examined the deposit routine and recognized that the share calculation mirrors a known problem (TOB‑YEARN‑003) where a “donation” can break share issuance. The defect is subtle because the contract does not emit an explicit error for a zero‑share mint, making it appear as a successful deposit. The problem is classified as a share‑dilution or zero‑share minting bug, a subclass of accounting inconsistencies that arise from improper handling of initial liquidity and rounding edge cases. To remediate, the contract should enforce a minimum amount of shares that are minted when totalSupply is zero (for example by minting a small amount to the zero address) and should include a require check that the computed shares are non‑zero for every deposit. Additionally, the share calculation could be adjusted to use a rounding‑up mechanism or to enforce a minimum liquidity threshold, ensuring that no deposit can result in a zero‑share allocation and preserving the integrity of the protocol’s accounting.

Overall, the vulnerability allows an attacker to cause legitimate users to lose their deposited assets without any on‑chain indication of failure, breaking the fundamental expectation that depositing tokens yields a proportional ownership token. Fixing the edge case restores correct economic behavior and protects users from silent loss of funds.

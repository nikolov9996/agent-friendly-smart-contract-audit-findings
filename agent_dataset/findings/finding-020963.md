---
id: 20963
severity: "High"
---

# Risk of reentrancy `onERC721Received` function to manipulate collateral token configs shares

## Description

```solidity
function onERC721Received(address, address from, uint256 tokenId, bytes calldata data)
    external
    override
    returns (bytes4)
{
    ...

    if {
        ...
    } else {
        uint256 oldTokenId = transformedTokenId;

        // if in transform mode - and a new position is sent - current position is replaced and returned
        if (tokenId != oldTokenId) {
            address owner = tokenOwner[oldTokenId];

            // set transformed token to new one
            transformedTokenId = tokenId;

            // copy debt to new token
            loans[tokenId] = Loan(loans[oldTokenId].debtShares);

            _addTokenToOwner(owner, tokenId);
            emit Add(tokenId, owner, oldTokenId);

            // clears data of old loan
            _cleanupLoan(oldTokenId, debtExchangeRateX96, lendExchangeRateX96, owner);

            //@audit can reenter with onERC721Received and call repay or borrow to call _updateAndCheckCollateral twice and manipulate collateral token configs

            // sets data of new loan
            _updateAndCheckCollateral(
                tokenId, debtExchangeRateX96, lendExchangeRateX96, 0, loans[tokenId].debtShares
            );
        }
    }

    return IERC721Receiver.onERC721Received.selector;
}
```
We should note that the `_cleanupLoan` function does return the old position token to the owner:
```solidity
function _cleanupLoan(
    uint256 tokenId,
    uint256 debtExchangeRateX96,
    uint256 lendExchangeRateX96,
    address owner
) internal {
    _removeTokenFromOwner(owner, tokenId);
    _updateAndCheckCollateral(
        tokenId,
        debtExchangeRateX96,
        lendExchangeRateX96,
        loans[tokenId].debtShares,
        0
    );
    delete loans[tokenId];
    nonfungiblePositionManager.safeTransferFrom(
        address(this),
        owner,
        tokenId
    );
    emit Remove(tokenId, owner);
}
```
The issue that can occur is that the `_cleanupLoan` is invoked before the `_updateAndCheckCollateral` call. So, a malicious owner can use the `onERC721Received` callback when receiving the old token to call the `borrow` function, which makes changes to `loans[tokenId].debtShares` and calls `_updateAndCheckCollateral`. When the call resumes, the `V3Vault.onERC721Received` function will call `_updateAndCheckCollateral` again, resulting in incorrect accounting of internal token configs debt shares (`tokenConfigs[token0].totalDebtShares` & `tokenConfigs[token1].totalDebtShares`) and potentially impacting the vault borrowing process negatively.

A malicious attacker could use the AutoRange transformation process to manipulate the internal token configs debt shares, potentially resulting in:

  * Fewer loans being allowed by the vault than expected.
  * A complete denial-of-service (DOS) for all borrow operations.

## Proof of Concept

Let’s use the following scenario to demonstrate the issue:

Before starting, we suppose the following states:

  * `tokenConfigs[token0].totalDebtShares = 10000`
  * `tokenConfigs[token1].totalDebtShares = 15000`
  * Bob has previously deposited a UniswapV3 position (which uses `token0` and `token1`) with `tokenId = 12` and borrowed `loans[tokenId = 12].debtShares = 1000` debt shares.
  * Bob calls the `transform` function to change the range of his position using the AutoRange transformer, which mints a new ERC721 token `tokenId = 20` for the newly arranged position and sends it to the vault.
  * Upon receiving the new token, the `V3Vault.onERC721Received` function is triggered. As we’re in transformation mode and the token ID is different, the second else block above will be executed.
  * `V3Vault.onERC721Received` will copy loan debt shares to the new token, so we’ll have `loans[tokenId = 20].debtShares = 1000`.
  * Then `V3Vault.onERC721Received` will invoke the `_cleanupLoan` function to clear the data of the old loan and transfer the old position token `tokenId = 12` back to Bob.
    * 5.1. `_cleanupLoan` will also call `_updateAndCheckCollateral` function to change `oldShares = 1000 --> newShares = 0` (remove old token shares), resulting in:
      * `tokenConfigs[token0].totalDebtShares = 10000 - 1000 = 9000`.
      * `tokenConfigs[token1].totalDebtShares = 15000 - 1000 = 14000`.
  * Bob, upon receiving the old position token, will also use the ERC721 `onERC721Received` callback to call the `borrow` function. He will borrow 200 debt shares against his new position token `tokenId = 20`.
    * 6.1. The `borrow` function will update the token debt shares from `loans[tokenId = 20].debtShares = 1000` to: `loans[tokenId = 20].debtShares = 1000 + 200 = 1200` (assuming the position is healthy).
    * 6.2. The `borrow` function will also invoke the `_updateAndCheckCollateral` function to change `oldShares = 1000 --> newShares = 1200` for `tokenId = 20`, resulting in:
      * `tokenConfigs[token0].totalDebtShares = 9000 + 200 = 9200`.
      * `tokenConfigs[token1].totalDebtShares = 14000 + 200 = 14200`.
  * Bob’s borrow call ends, and the `V3Vault.onERC721Received` call resumes. `_updateAndCheckCollateral` gets called again, changing `oldShares = 0 --> newShares = 1200` (as the borrow call changed the token debt shares), resulting in:
    * `tokenConfigs[token0].totalDebtShares = 9200 + 1200 = 10400`.
    * `tokenConfigs[token1].totalDebtShares = 14200 + 1200 = 15400`.

Now, let’s assess what Bob managed to achieve by taking a normal/honest transformation process (without using the `onERC721Received` callback) and then a borrow operation scenario:

  * Normally, when `V3Vault.onERC721Received` is called, it shouldn’t change the internal token configs debt shares (`tokenConfigs[token0].totalDebtShares` & `tokenConfigs[token1].totalDebtShares`). After a normal `V3Vault.onERC721Received`, we should still have:
    * `tokenConfigs[token0].totalDebtShares = 10000`.
    * `tokenConfigs[token1].totalDebtShares = 15000`.
  * Then, when Bob borrows 200 debt shares against the new token, we should get:
    * `tokenConfigs[token0].totalDebtShares = 10000 + 200 = 10200`.
    * `tokenConfigs[token1].totalDebtShares = 15000 + 200 = 15200`.

We observe that by using the `onERC721Received` callback, Bob managed to increase the internal token configs debt shares (`tokenConfigs[token0].totalDebtShares` & `tokenConfigs[token1].totalDebtShares`) by 200 debt shares more than expected.

This means that Bob, by using this attack, has manipulated the internal token configs debt shares, making the vault believe it has 200 additional debt shares. Bob can repeat this attack multiple times until he approaches the limit represented by `collateralValueLimitFactorX32` and `collateralValueLimitFactorX32` multiplied by the amount of asset lent as shown below:
```solidity
uint256 lentAssets = _convertToAssets(
    totalSupply(),
    lendExchangeRateX96,
    Math.Rounding.Up
);
uint256 collateralValueLimitFactorX32 = tokenConfigs[token0]
    .collateralValueLimitFactorX32;
if (
    collateralValueLimitFactorX32 < type(uint32).max &&
    _convertToAssets(
        tokenConfigs[token0].totalDebtShares,
        debtExchangeRateX96,
        Math.Rounding.Up
    ) >
    (lentAssets * collateralValueLimitFactorX32) / Q32
) {
    revert CollateralValueLimit();
}
collateralValueLimitFactorX32 = tokenConfigs[token1]
    .collateralValueLimitFactorX32;
if (
    collateralValueLimitFactorX32 < type(uint32).max &&
    _convertToAssets(
        tokenConfigs[token1].totalDebtShares,
        debtExchangeRateX96,
        Math.Rounding.Up
    ) >
    (lentAssets * collateralValueLimitFactorX32) / Q32
) {
    revert CollateralValueLimit();
}
```
Then, when other borrowers try to call the `borrow` function, it will revert because `_updateAndCheckCollateral` will trigger the `CollateralValueLimit` error, thinking there is too much debt already. However, this is not the case, as the internal token configs debt shares have been manipulated (increased) by an attacker (Bob).

This attack is irreversible because there is no way to correct the internal token configs debt shares (`tokenConfigs[token0].totalDebtShares` & `tokenConfigs[token1].totalDebtShares`), and the vault will remain in that state, not allowing users to borrow, resulting in no interest being accrued and leading to financial losses for the lenders and the protocol.

## Recommendation

```solidity
function onERC721Received(address, address from, uint256 tokenId, bytes calldata data)
    external
    override
    returns (bytes4)
{
    ...

    if {
        ...
    } else {
        uint256 oldTokenId = transformedTokenId;

        // if in transform mode - and a new position is sent - current position is replaced and returned
        if (tokenId != oldTokenId) {
            address owner = tokenOwner[oldTokenId];

            // set transformed token to new one
            transformedTokenId = tokenId;

            // copy debt to new token
            loans[tokenId] = Loan(loans[oldTokenId].debtShares);

            _addTokenToOwner(owner, tokenId);
            emit Add(tokenId, owner, oldTokenId);

    //          // clears data of old loan
    //          _cleanupLoan(oldTokenId, debtExchangeRateX96, lendExchangeRateX96, owner);

            // sets data of new loan
            _updateAndCheckCollateral(
                tokenId, debtExchangeRateX96, lendExchangeRateX96, 0, loans[tokenId].debtShares
            );

    //          // clears data of old loan
    //          _cleanupLoan(oldTokenId, debtExchangeRateX96, lendExchangeRateX96, owner);
        }
    }

    return IERC721Receiver.onERC721Received.selector;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a reentrancy flaw that occurs in the ERC721 receiver callback of a vault that manages collateralized positions. When the vault receives a new NFT representing a transformed position, the onERC721Received function copies the loan data to the new token, calls an internal cleanup routine for the old token, and then updates the collateral accounting. The cleanup routine transfers the old NFT back to the user and invokes _updateAndCheckCollateral before the vault finishes its own _updateAndCheckCollateral call. Because the transfer triggers the recipient's onERC721Received callback, a malicious owner can invoke borrow (or repay) from within that callback, causing the vault to execute _updateAndCheckCollateral a second time while the first call has not yet completed. This double execution manipulates the internal accounting of total debt shares for each underlying token (tokenConfigs.totalDebtShares), inflating the recorded debt without any real borrowing. The inflated debt can push the vault past its collateral value limit, causing subsequent borrow attempts to revert with a CollateralValueLimit error, effectively denying service to all users. The issue is discovered during a security audit that examined the order of internal calls and identified that the cleanup function performs an external call before the vault’s final accounting step. It is hard to notice because the contract appears to correctly transfer the old position back to the owner, and the reentrancy only manifests when the owner deliberately crafts a callback that calls borrow during the token receipt. From a user’s perspective, a borrower expects a normal transformation to leave the vault’s debt totals unchanged, but after the attack the protocol reports higher total debt, leading to unexpected transaction failures and a vault that no longer accepts new loans. The bug belongs to the class of reentrancy vulnerabilities caused by external calls (safeTransferFrom) placed before state updates, combined with mutable accounting functions that can be called multiple times. The recommended mitigation is to either move the cleanup logic after the final collateral update, eliminate the external call from the critical path, or protect the function with a reentrancy guard so that borrow or repay cannot be invoked from within onERC721Received. By ensuring that state changes to totalDebtShares are performed atomically and after all external interactions, the vault’s accounting integrity is preserved and the denial‑of‑service scenario is avoided.

---
id: 21200
severity: "High"
---

# SiloConnector `_getPositionTVL` miscalculate the TVL position

## Description

```solidity
`_getPositionTVL` from SiloConnector calculates wrongly the position’s TVL thus affecting the share price at which shares are minted / redeemed from the protocol.
```

## Proof of Concept

```solidity
Each connector implements a `_getPositionTVL` used to return the value of funds, in base token, its corresponding protocol holds.

This information is used by `AccountingManager` to calculate the total assets of the vault and used by 4626 standard to calculate the shares price.

The problem is that SiloConnector miscalculate the value sent to SiloConnector protocol.
    
        function _getPositionTVL(HoldingPI memory p, address base) public view override returns (uint256 tvl) {
            PositionBP memory bp = registry.getPositionBP(vaultId, p.positionId);
            (address siloToken) = abi.decode(bp.data, (address));
            ISilo silo = ISilo(siloRepository.getSilo(siloToken));
            (address[] memory assets, IBaseSilo.AssetStorage[] memory assetsS) = silo.getAssetsWithState();
            uint256 totalDepositAmount = 0;
            uint256 totalBAmount = 0;
            for (uint256 i = 0; i < assets.length; i++) {
                uint256 depositAmount = IERC20(assetsS[i].collateralToken).balanceOf(address(this));
                depositAmount += IERC20(assetsS[i].collateralOnlyToken).balanceOf(address(this));
                uint256 borrowAmount = IERC20(assetsS[i].debtToken).balanceOf(address(this));
                if (depositAmount == 0 && borrowAmount == 0) {
                    continue;
                }
                uint256 price = _getValue(assets[i], base, 1e18);
                totalDepositAmount += depositAmount * price / 1e18;
                totalBAmount += borrowAmount * price / 1e18;
            }
            tvl = totalDepositAmount - totalBAmount;
        }

This function calls `silo.getAssetsWithState()` to get a list of assets and data associated with them. Then for each asset:

  1. calculates `depositAmount` as sum of 2 different token balances: `collateralToken` and `collateralOnlyToken`
  2. retrieve the `borrowAmount` as the balance of a 3rd token named `debtToken`.
  3. get the price of asset (eg. `assets[i]`) in ‘base’ token
  4. calculates and save the deposited and borrowed amounts

After all assetes have been looped over, the tvl is calculated as the difference between deposits and debt amounts:  
`tvl = totalDepositAmount - totalBAmount`

There are 2 problems here:

  1. `collateralToken` and `collateralOnlyToken` are 2 different tokens and protocol is summing them as if they represents amounts of the same token.
  2. protocol is multiplying the price of `assets[i]` by the amounts of shares and not the underlying token (which is `assets[i]`).

All 3 tokens ( `collateralToken`, `collateralOnlyToken` and `debtToken`) are share tokens with the same underlying asset but have different purposes and different exchange rate.

To help us creating a better picture of what each token represent we can [look](https://github.com/silo-finance/silo-core-v1/blob/e5d16f201ab2139829d45ed881532c936249d3a5/contracts/interfaces/IBaseSilo.sol#L11-L27) how `AssetStorage` struct looks like:
    
        /// @dev Storage struct that holds all required data for a single token market
        struct AssetStorage {
            /// @dev Token that represents a share in totalDeposits of Silo
            IShareToken collateralToken;
            /// @dev Token that represents a share in collateralOnlyDeposits of Silo
            IShareToken collateralOnlyToken;
            /// @dev Token that represents a share in totalBorrowAmount of Silo
            IShareToken debtToken;
    
            /// @dev COLLATERAL: Amount of asset token that has been deposited to Silo with interest earned by depositors.
            /// It also includes token amount that has been borrowed.
            uint256 totalDeposits;
            /// @dev COLLATERAL ONLY: Amount of asset token that has been deposited to Silo that can be ONLY used
            /// as collateral. These deposits do NOT earn interest and CANNOT be borrowed.
            uint256 collateralOnlyDeposits;
            /// @dev DEBT: Amount of asset token that has been borrowed with accrued interest.
            uint256 totalBorrowAmount;
        }

To make an analogy, it is like summing peanuts amount with fruits amount and then multiplying it by the peanut jelly price.
```

## Recommendation

```solidity
In the for loop, after you got the share tokens balances with `balanceOf`:

  * convert all 3 share tokens balances to underlying token (eg. `underlyingTotalDeposits, underlyingCollateralOnlyDeposits, underlyingBorrowAmount`)
  * sum underlying deposits : `underlyingTotalDeposits = underlyingTotalDeposits + underlyingCollateralOnlyDeposits`
  * get the price of the underlying asset
  * calculate the `totalDepositAmount` and `totalBAmount` using the calculated `underlyingTotalDeposits` and `underlyingBorrowAmount` and price.
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the SiloConnector contract's internal function that reports the total value locked (TVL) for a position. The function iterates over each asset returned by the Silo protocol and adds together the balances of two share tokens – collateralToken and collateralOnlyToken – as if they were amounts of the same underlying asset. It then multiplies those share balances by the market price of the underlying token, without converting the share tokens to their underlying amounts. Because each share token has its own exchange rate and represents a different portion of the protocol's accounting (total deposits, collateral‑only deposits, and total borrow amount), the calculation produces a TVL that can be significantly higher or lower than the real value. The AccountingManager and the ERC‑4626 share‑price logic rely on this TVL to mint and redeem vault shares. When the TVL is inflated, the contract may mint more shares than the underlying assets justify; when it is deflated, users redeem fewer assets than they expect. An attacker can exploit the mismatch by depositing assets that are represented only by the collateralOnlyToken, which does not earn interest, causing the TVL to be overstated, then redeeming shares later to extract excess value. The impact is a distortion of the share price, potential loss of user funds, and a breach of the protocol’s accounting invariants. The bug appears whenever the connector’s _getPositionTVL function is called – typically during every deposit, withdrawal, or accounting snapshot – and affects any user who interacts with the vault, as well as the protocol’s overall asset accounting. It was discovered during a manual audit that compared the Silo protocol’s internal accounting fields with the values returned by the connector, revealing that the share‑token balances were being summed incorrectly. The issue is subtle because the three tokens share the same underlying asset, so a superficial inspection may not notice the differing exchange rates, and the resulting TVL discrepancy can be hidden by other protocol operations. The proper fix is to convert each share‑token balance to its underlying asset amount using the token’s exchange rate, sum the true underlying deposits (totalDeposits plus collateralOnlyDeposits), and then subtract the true underlying borrow amount before applying the price conversion. In other words, the TVL calculation must operate on underlying token quantities, not on share‑token balances, and must treat collateral‑only deposits separately from interest‑bearing deposits. From a user’s perspective the symptom is that the vault’s share price appears unusually high, yet when a user attempts to withdraw they receive less of the base token than expected, or the displayed balance may drop to zero despite a prior deposit. This constitutes a classic accounting‑logic bug where share‑token accounting is conflated with underlying asset accounting, leading to incorrect valuation and potential fund loss.

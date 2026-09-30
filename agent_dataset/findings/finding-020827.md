---
id: 20827
severity: "High"
---

# Wrong use of `nftID` to check if a `PowerFarm` position is an Aave position

## Description

When a `PowerFarm` position is created its `keyId` is used as a key in the `isAave` mapping to indicate if it is an Aave position or not. The `keyId` is the index of the Power Farm NFT linked with the position.

[PendlePowerManager.sol#L129-L130](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/PowerFarms/PendlePowerFarm/PendlePowerManager.sol#L129C1-L130C1)

```solidity
    isAave[keyId] = _isAave;
```

The `keyId` is also linked with another `nftId`. This other `nftId` is used to hold the `keyId`s Power Farm position in the `WiseLending` contract. They are linked together in the `farmingKeys` mapping of the `MinterReserver` contract.

[MinterReserver.sol#L88C1-L91C46](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/PowerFarms/PowerFarmNFTs/MinterReserver.sol#L88C1-L91C46)

```solidity
    uint256 keyId = _getNextReserveKey();

    reservedKeys[_userAddress] = keyId;
    farmingKeys[keyId] = _wiseLendingNFT;
```

The issue is the check if a position is an Aave position is done using the `WiseLending` `nftId` instead of the Power Farm’s `keyId`. This occurs five times in the code:

It is used in `getLiveDebtRatio()` to know the pool token borrowed so the `borrowShares` can be retrieved.

[PendlePowerFarm.sol#L64-L70](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/PowerFarms/PendlePowerFarm/PendlePowerFarm.sol#L64-L70)

```solidity
    uint256 borrowShares = isAave[_nftId]
        ? _getPositionBorrowSharesAave(
            _nftId
        )
        : _getPositionBorrowShares(
            _nftId
    );
```

It is used in `_manuallyPaybackShares()` to know the pool token to pay back.

[PendlePowerFarm.sol#L127-L129](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/PowerFarms/PendlePowerFarm/PendlePowerFarm.sol#L127-L129)

```solidity
    if (isAave[_nftId] == true) {
        poolAddress = AAVE_WETH_ADDRESS;
    }
```

It is used in `checkDebtRatio()` to know the pool token borrowed so the `borrowShares` can be retrieved.

[PendlePowerFarmMathLogic.sol#L396-L402](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/PowerFarms/PendlePowerFarm/PendlePowerFarmMathLogic.sol#L396-L402)

```solidity
    uint256 borrowShares = isAave[_nftId]
        ? _getPositionBorrowSharesAave(
            _nftId
        )
        : _getPositionBorrowShares(
            _nftId
    );
```

It is used in `_coreLiquidation()` to select a token to payback and to know the pool token borrowed so the `borrowShares` can be retrieved.

[PendlePowerFarmLeverageLogic.sol#L575-L590](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/PowerFarms/PendlePowerFarm/PendlePowerFarmLeverageLogic.sol#L575-L590)

```solidity
    address paybackToken = isAave[_nftId] == true
        ? AAVE_WETH_ADDRESS
        : WETH_ADDRESS;

    paybackAmount = WISE_LENDING.paybackAmount(
        paybackToken,
        _shareAmountToPay
    );

    uint256 cutoffShares = isAave[_nftId] == true
        ? _getPositionBorrowSharesAave(_nftId)
            * FIVTY_PERCENT
            / PRECISION_FACTOR_E18
        : _getPositionBorrowShares(_nftId)
            * FIVTY_PERCENT
            / PRECISION_FACTOR_E18;
```

These have the following effects:

* For `getLiveDebtRatio()`, users would get zero when they try to retrieve their debt ratio.
* For `_manuallyPaybackShares()` users won’t be able to pay back their shares manually from the `PowerFarm` contract since it’ll fetch zero shares as borrow shares.
* The last two instances are used in liquidation and allow a malicious user to have a position that can’t be liquidated even though it is eligible for liquidation. The malicious user can:

  1. Create an Aave `PowerFarm` position.
  2. The position becomes eligible for liquidation after some price changes.
  3. Liquidators cannot liquidate the position because the call to `_coreLiquidation` first calls `checkDebtRatio()` which uses the wrong `borrowShares` to calculate the debt ratio and returns true. Thus, causing a revert.

[PendlePowerFarmLeverageLogic.sol#L571C1-L574C1](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/PowerFarms/PendlePowerFarm/PendlePowerFarmLeverageLogic.sol#L571C1-L574C1)

```solidity
    if (_checkDebtRatio(_nftId) == true) {
        revert DebtRatioTooLow();
    }
```

## Proof of Concept

There are 3 tests below and they can all be run in [PendlePowerFarmControllerBase.t.sol](https://github.com/code-423n4/2024-02-wise-lending/blob/main/contracts/PowerFarms/PendlePowerFarmController/PendlePowerFarmControllerBase.t.sol).

* `testAaveGetLiveDebtRatio()` shows that `getLiveDebtRatio()` returns zero.
* `testAaveManuallyPayback()` shows that borrowed tokens can’t be paid back using `manuallyPaybackShares()`.
* `testCannotLiquidate()` shows that Aave positions cannot be liquidated.

```solidity
function testAaveGetLiveDebtRatio() public cheatSetup(true){
    _prepareAave();
    uint256 keyID = powerFarmManagerInstance.enterFarm(
        true,
        1 ether,
        15 ether,
        entrySpread
    );

    uint nftId = powerFarmManagerInstance.farmingKeys(keyID);
    // gets borrow shares of weth instead of aeth
    uint ratio = powerFarmManagerInstance.getLiveDebtRatio(nftId);
    assertEq(ratio, 0);
}

function testAaveManuallyPayback() public cheatSetup(true){
    _prepareAave();
    uint256 keyID = powerFarmManagerInstance.enterFarm(
        true,
        1 ether,
        15 ether,
        entrySpread
    );

    uint nftId = powerFarmManagerInstance.farmingKeys(keyID);
    uint borrowShares = wiseLendingInstance.getPositionBorrowShares(nftId, AWETH);
    // tries to payback weth instead of aweth and reverts with an arithmetic underflow
    // since the position has 0 weth borrow shares
    vm.expectRevert();
    powerFarmManagerInstance.manuallyPaybackShares(keyID, borrowShares);
}
    
error DebtRatioTooLow();
function testCannotLiquidate() public cheatSetup(true){
    _prepareAave();
    uint256 keyID = powerFarmManagerInstance.enterFarm(
        true,
        1 ether,
        15 ether,
        entrySpread
    );

    // increase collateral factors to make position eligible for liquidation
    wiseLendingInstance.setPoolParameters(AWETH, 99e16, type(uint256).max); // increasw Wiselending coll factor
    vm.store(address(powerFarmManagerInstance), bytes32(uint(2)), bytes32(uint(99e16))); //increasw PowerFarm coll factor
    assertEq(powerFarmManagerInstance.collateralFactor(), 99e16);

    uint nftId = powerFarmManagerInstance.farmingKeys(keyID);
    uint borrowShares = wiseLendingInstance.getPositionBorrowShares(nftId, AWETH);
    // will revert if it can't be liquidated
    wiseSecurityInstance.checksLiquidation(nftId, AWETH, borrowShares);

    uint nftIdLiquidator = positionNftsInstance.mintPosition();

    vm.expectRevert(DebtRatioTooLow.selector);
    powerFarmManagerInstance.liquidatePartiallyFromToken(nftId, nftIdLiquidator, borrowShares );
}
```

## Recommendation

Consider checking if a position is an Aave position using the `keyId` of the position.

[PendlePowerFarm.sol#L64-L70](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/PowerFarms/PendlePowerFarm/PendlePowerFarm.sol#L64-L70)

```solidity
-       uint256 borrowShares = isAave[_nftId]
+       uint256 borrowShares = isAave[keyId]
            ? _getPositionBorrowSharesAave(
                _nftId
            )
            : _getPositionBorrowShares(
                _nftId
        );
```

[PendlePowerFarm.sol#L127-L129](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/PowerFarms/PendlePowerFarm/PendlePowerFarm.sol#L127-L129)

```solidity
-       if (isAave[_nftId] == true) {
+       if (isAave[keyId] == true) {
            poolAddress = AAVE_WETH_ADDRESS;
        }
```

[PendlePowerFarmMathLogic.sol#L396-L402](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/PowerFarms/PendlePowerFarm/PendlePowerFarmMathLogic.sol#L396-L402)

```solidity
-        uint256 borrowShares = isAave[_nftId]
+        uint256 borrowShares = isAave[keyId]
            ? _getPositionBorrowSharesAave(
                _nftId
            )
            : _getPositionBorrowShares(
                _nftId
        );
```

[PendlePowerFarmLeverageLogic.sol#L575-L590](https://github.com/code-423n4/2024-02-wise-lending/blob/79186b243d8553e66358c05497e5ccfd9488b5e2/contracts/PowerFarms/PendlePowerFarm/PendlePowerFarmLeverageLogic.sol#L575-L590)

```solidity
-        address paybackToken = isAave[_nftId] == true
+        address paybackToken = isAave[keyId] == true
            ? AAVE_WETH_ADDRESS
            : WETH_ADDRESS;

        paybackAmount = WISE_LENDING.paybackAmount(
            paybackToken,
            _shareAmountToPay
        );

-       uint256 cutoffShares = isAave[_nftId] == true
+       uint256 cutoffShares = isAave[keyId] == true
            ? _getPositionBorrowSharesAave(_nftId)
                * FIVTY_PERCENT
                / PRECISION_FACTOR_E18
            : _getPositionBorrowShares(_nftId)
                * FIVTY_PERCENT
                / PRECISION_FACTOR_E18;
```

While this is marked as High, we would like to bring this to a Medium, as there is still a way to liquidate such nft/user should that even occur (depending if there’s AavePool present etc).

@vonMangoldt can provide details on how this can be mitigated and user can still be liquidated even if they would have a chance to enter with the wrong `isAave` flag.

Mitigated [here](https://github.com/wise-foundation/lending-audit/commit/ac68b5a93976969d582301fee9f873ecec606df9).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from an identifier mismatch in the PowerFarm contracts where the mapping that records whether a position is an Aave position (isAave) is keyed by the internal keyId of the PowerFarm NFT, but several functions mistakenly query this mapping using the external WiseLending nftId. The root cause is that the keyId, which is the index of the PowerFarm NFT, is linked to the WiseLending nftId through the farmingKeys mapping, yet the code continues to use the WiseLending nftId as the lookup key. This incorrect lookup causes the isAave flag to be read as false for genuine Aave positions, leading to a cascade of logical errors. When a user creates an Aave‑backed PowerFarm position, functions such as getLiveDebtRatio, manuallyPaybackShares, and the liquidation pathway retrieve zero borrow shares because they consult isAave with the wrong identifier. Consequently, the debt ratio reported to the user is zero, manual repayment attempts revert due to arithmetic underflow, and liquidation attempts revert with the custom DebtRatioTooLow error even though the position is technically eligible for liquidation. The impact affects any user holding an Aave PowerFarm position, the protocol’s accounting integrity, and liquidators who are unable to enforce collateral enforcement, potentially leaving funds locked or unaccounted for. The bug manifests only for Aave‑type positions; non‑Aave positions operate correctly, making the issue subtle and easy to miss during casual testing. It was discovered through targeted unit tests that exercised the Aave path, revealing zero ratios and revert patterns. The class of bug can be described as an identifier‑based mapping misuse or key mismatch, a common source of accounting failures in smart contracts. From a user’s perspective the symptoms are a debt ratio that reads zero, inability to manually repay borrowed shares, and liquidation transactions that fail with an unexpected error, contradicting the expectation that the protocol should allow repayment and liquidation. The fix consists of consistently using the internal keyId when accessing the isAave mapping across all affected functions, thereby aligning the logical flag with the correct position identifier and restoring correct borrow‑share calculations, repayment flows, and liquidation logic.

---
id: 25015
severity: "Medium"
---

# An attacker can manipulate omniChainData.cdsPoolValue by breaking protocol.

## Description



## Proof of Concept

## Impact

- In case of increasing, `cdsPoolValue` can be much bigger than normal. Then, borrowing is allowed even if protocol is really under water.
- In case of decreasing, `cdsPoolValue` can be decreased so that ratio is small enough to touch `(2 * RATIO_PRECISION)`. Then, borrowing can be DOSed even if cds have enough funds. And withdrawal from CDS can be DOSed.

## Recommendation

`borrowing.sol#depositTokens()` function has to be modified as follows.

```solidity
    function depositTokens(
        BorrowDepositParams memory depositParam
    ) external payable nonReentrant whenNotPaused(IMultiSign.Functions(0)) {
        // Assign options for lz contract, here the gas is hardcoded as 400000, we got this through testing by iteration
        bytes memory _options = OptionsBuilder.newOptions().addExecutorLzReceiveOption(400000, 0);
        // calculting fee
        MessagingFee memory fee = globalVariables.quote(
            IGlobalVariables.FunctionToDo(1),
            depositParam.assetName,
            _options,
            false
        );
        // Get the exchange rate for a collateral and eth price
        (uint128 exchangeRate, uint128 ethPrice) = getUSDValue(assetAddress[depositParam.assetName]);

        totalNormalizedAmount = BorrowLib.deposit(
            BorrowLibDeposit_Params(
                LTV,
                APR,
                lastCumulativeRate,
                totalNormalizedAmount,
                exchangeRate,
                ethPrice,
                lastEthprice
            ),
            depositParam,
            Interfaces(treasury, globalVariables, usda, abond, cds, options),
            assetAddress
        );

        //Call calculateCumulativeRate() to get currentCumulativeRate
        calculateCumulativeRate();
        lastEventTime = uint128(block.timestamp);
++      lastEthprice = ethPrice;

        // Calling Omnichain send function
        globalVariables.send{value: fee.nativeFee}(
            IGlobalVariables.FunctionToDo(1),
            depositParam.assetName,
            fee,
            _options,
            msg.sender
        );
    }
```

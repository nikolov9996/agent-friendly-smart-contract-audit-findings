---
id: 17942
severity: "High"
---

# `FeeRefund.tokenGasPriceFactor` is not included in signed transaction data allowing the submitter to steal funds

## Description

[contracts/smart-contract-wallet/SmartAccount.sol#L288](https://github.com/code-423n4/2023-01-biconomy/blob/main/scw-contracts/contracts/smart-contract-wallet/SmartAccount.sol#L288)  
[contracts/smart-contract-wallet/SmartAccount.sol#L429-L444](https://github.com/code-423n4/2023-01-biconomy/blob/main/scw-contracts/contracts/smart-contract-wallet/SmartAccount.sol#L429-L444)

The submitter of a transaction is paid back the transaction’s gas costs either in ETH or in ERC20 tokens. With ERC20 tokens the following formula is used: $(gasUsed + baseGas) \\* gasPrice / tokenGasPriceFactor$. `baseGas`, `gasPrice`, and `tokenGasPriceFactor` are values specified by the tx submitter. Since you don’t want the submitter to choose arbitrary values and pay themselves as much as they want, those values are supposed to be signed off by the owner of the wallet. The signature of the user is included in the tx so that the contract can verify that all the values are correct. But, the `tokenGasPriceFactor` value is not included in those checks. Thus, the submitter is able to simulate the tx with value $x$, get the user to sign that tx, and then submit it with $y$ for `tokenGasPriceFactor`. That way they can increase the actual gas repayment and steal the user’s funds.

## Proof of Concept

In `encodeTransactionData()` we can see that `tokenGasPriceFactor` is not included:
    
    ```solidity
        function encodeTransactionData(
            Transaction memory _tx,
            FeeRefund memory refundInfo,
            uint256 _nonce
        ) public view returns (bytes memory) {
            bytes32 safeTxHash =
                keccak256(
                    abi.encode(
                        ACCOUNT_TX_TYPEHASH,
                        _tx.to,
                        _tx.value,
                        keccak256(_tx.data),
                        _tx.operation,
                        _tx.targetTxGas,
                        refundInfo.baseGas,
                        refundInfo.gasPrice,
                        refundInfo.gasToken,
                        refundInfo.refundReceiver,
                        _nonce
                    )
                );
            return abi.encodePacked(bytes1(0x19), bytes1(0x01), domainSeparator(), safeTxHash);
        }
    ```

The value is used to determine the gas repayment in `handlePayment()` and `handlePaymentRevert()`:
    
    ```solidity
        function handlePayment(
            uint256 gasUsed,
            uint256 baseGas,
            uint256 gasPrice,
            uint256 tokenGasPriceFactor,
            address gasToken,
            address payable refundReceiver
        ) private nonReentrant returns (uint256 payment) {
            // uint256 startGas = gasleft();
            // solhint-disable-next-line avoid-tx-origin
            address payable receiver = refundReceiver == address(0) ? payable(tx.origin) : refundReceiver;
            if (gasToken == address(0)) {
                // For ETH we will only adjust the gas price to not be higher than the actual used gas price
                payment = (gasUsed + baseGas) * (gasPrice < tx.gasprice ? gasPrice : tx.gasprice);
                (bool success,) = receiver.call{value: payment}("");
                require(success, "BSA011");
            } else {
                payment = (gasUsed + baseGas) * (gasPrice) / (tokenGasPriceFactor);
                require(transferToken(gasToken, receiver, payment), "BSA012");
            }
            // uint256 requiredGas = startGas - gasleft();
            //console.log("hp %s", requiredGas);
        }
    ```

That’s called at the end of `execTransaction()`:
    
    ```solidity
                if (refundInfo.gasPrice > 0) {
                    //console.log("sent %s", startGas - gasleft());
                    // extraGas = gasleft();
                    payment = handlePayment(startGas - gasleft(), refundInfo.baseGas, refundInfo.gasPrice, refundInfo.tokenGasPriceFactor, refundInfo.gasToken, refundInfo.refundReceiver);
                    emit WalletHandlePayment(txHash, payment);
                }
    ```

As an example, given that:

  * `gasUsed = 1,000,000`
  * `baseGas = 100,000`
  * `gasPrice = 10,000,000,000` (10 gwei)
  * `tokenGasPriceFactor = 18`

You get $(1,000,000 + 100,000) \\* 10,000,000,000 / 18 = 6.1111111e14$. If the submitter executes the transaction with `tokenGasPriceFactor = 1` they get $1.1e16$ instead, i.e. 18 times more.

## Recommendation

`tokenGasPriceFactor` should be included in the encoded transaction data and thus verified by the user’s signature.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an omission in the transaction signing process of the "SmartAccount" contract. When a user authorises a transaction that includes a fee‑refund in ERC20 tokens, the contract expects the submitter to provide three parameters—baseGas, gasPrice and tokenGasPriceFactor—to compute the token repayment. The user’s signature is verified against a hash that includes baseGas and gasPrice, but the tokenGasPriceFactor is not part of the signed data. Because the factor is omitted, a malicious relayer can present the user with a transaction that contains a reasonable tokenGasPriceFactor, obtain the user’s signature, and then replace the factor with a much smaller value (e.g., 1 instead of 18) when actually submitting the transaction. The repayment formula (gasUsed + baseGas) * gasPrice / tokenGasPriceFactor) therefore yields a payment that is up to the ratio of the original factor to the manipulated one, allowing the submitter to claim an excessive amount of tokens from the wallet. The exploit can be carried out whenever the wallet is used with ERC20 fee‑refunds and the owner relies on the signed parameters for security. The impact is a direct loss of funds from the wallet: the owner sees a token balance reduced by an amount far larger than the gas actually consumed, while the relayer receives the over‑paid tokens. The issue was discovered during a manual audit of the SmartAccount contract by reviewing the encodeTransactionData function and noticing that tokenGasPriceFactor is omitted from the signed hash. It is hard to notice because the contract still performs a signature check and the payment logic appears correct; the missing field is subtle and does not raise compiler warnings. The bug belongs to the class of “missing‑parameter‑in‑signature‑verification” or “under‑validated payment calculation” vulnerabilities, where a value that influences monetary transfer is not covered by the user’s consent. From a user’s perspective the UI may show a normal transaction execution but the token balance drops unexpectedly or the refund amount is much higher than anticipated, violating the expectation that the refund equals the actual gas cost. The correct fix is to include tokenGasPriceFactor in the encoded transaction data that is hashed and signed, and to verify that the signed value matches the one used in handlePayment, thereby ensuring that the user explicitly authorises the exact factor used for the repayment calculation.

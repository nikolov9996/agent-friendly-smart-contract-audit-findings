---
id: 1680
severity: "High"
---

# Gas pricing can be used to extort funds from users of SChain owner

## Description

```solidity
The function `refundGasByUser()` can be exploited by the message sender to drain nodes and SChain owners of their balances when processing incoming messages.

When a node collates a set of exits from an SChain to Ethereum, they are submitted on-chain via `MessageProxyForMainnet.sol`. For each message to a registered contract the user is required to pay for the refund via `CommunityPool.refundGasByUser()`.

The issue occurs in `CommunityPool.refundGasByUser()` as the amount to be refunded is calculated as `uint amount = tx.gasprice * gas;`, where `gas` is the gas used by the message. Since `tx.gasprice` is set by the node and there is no upper bounds on the price. Since EIP1559 the gas price is `BaseFee + Tip` and although `Base` is predetermined `Tip` is any arbitrary non-zero integer.

The attack is for a node to set an excessively high `tx.gasprice` which will be refunded out of the balance of the user who initiated the outgoing transaction or if that user has insufficient balance then from the SChain owner. Since the node submitting the transaction is refunded for their gas they do not lose from setting a higher gas price.

The impact of the attack is that the user requesting the exit and/or the SChain owner may have their ETH balances depleted to refund the submitter. The impact is worsened as if the user has insufficient balance a message will be sent to the SChain preventing them from making further exits until they have sufficient balance.

Note a similar issue may be seen in `IWallets.refundGasBySchain()` depending on how the gas calculations are performed (they are not in scope but the `TestWallet` also uses `tx.gasprice` in the same manner).
```

## Proof of Concept

```solidity
Processing incoming messages in `MessageProxyForMainnet.sol`
    
            for (uint256 i = 0; i < messages.length; i++) {
                gasTotal = gasleft();
                if (isContractRegistered(bytes32(0), messages[i].destinationContract)) {
                    address receiver = _getGasPayer(fromSchainHash, messages[i], startingCounter + i);
                    _callReceiverContract(fromSchainHash, messages[i], startingCounter + i);
                    notReimbursedGas += communityPool.refundGasByUser(
                        fromSchainHash,
                        payable(msg.sender),
                        receiver,
                        gasTotal - gasleft() + additionalGasPerMessage
                    );
                } else {
                    _callReceiverContract(fromSchainHash, messages[i], startingCounter + i);
                    notReimbursedGas += gasTotal - gasleft() + additionalGasPerMessage;
                }
            }

Refunding gas in `CommunityPool.sol`
    
        function refundGasByUser(
            bytes32 schainHash,
            address payable node,
            address user,
            uint gas
        )
            external
            override
            onlyMessageProxy
            returns (uint)
        {
            require(node != address(0), "Node address must be set");
            if (!activeUsers[user][schainHash]) {
                return gas;
            }
            uint amount = tx.gasprice * gas;
            if (amount > _userWallets[user][schainHash]) {
                amount = _userWallets[user][schainHash];
            }
            _userWallets[user][schainHash] = _userWallets[user][schainHash] - amount;
            if (!_balanceIsSufficient(schainHash, user, 0)) {
                activeUsers[user][schainHash] = false;
                messageProxy.postOutgoingMessage(
                    schainHash,
                    schainLinks[schainHash],
                    Messages.encodeLockUserMessage(user)
                );
            }
            node.sendValue(amount);
            return (tx.gasprice * gas - amount) / tx.gasprice;
        }
```

## Recommendation

```solidity
One solution to avoid excessive over refunding of gas fees is to use a gas price oracle rather than `tx.gasprice`.

An alternate solution is to set a maximum gas price and have some incentives for the node submitting at a gas price below the maximum.
```

**[cstrangedk (SKALE) resolved](https://github.com/code-423n4/2022-02-skale-findings/issues/28#issuecomment-1176670089):**  
Resolved via <https://github.com/skalenetwork/IMA/pull/1165/>

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the gas‑refund routine of the community pool contract, where the amount reimbursed to a node that processes an outbound message is calculated as `tx.gasprice * gas`. Because `tx.gasprice` is supplied by the transaction sender, a malicious node that submits the transaction can arbitrarily inflate the gas price by adding a large tip (as allowed by EIP‑1559). No upper bound or validation is performed on this value, so the refund amount can far exceed the actual cost of execution. When the refund is executed, the contract first checks whether the user who initiated the exit has a sufficient balance in the per‑SChain wallet; if the user’s balance is insufficient, the contract deducts the maximum available amount and then deactivates the user, preventing further exits until the balance is replenished. Consequently, a node can set an excessively high `tx.gasprice`, trigger the refund, and cause the user’s or the SChain owner’s ETH balance to be drained, while the node receives the over‑refunded amount without incurring any cost. The attack becomes possible whenever a node collates exits and calls `CommunityPool.refundGasByUser`, which is the standard flow for processing incoming messages on the mainnet bridge. The issue was discovered during a systematic security audit that examined the accounting logic of message refunds and identified that the gas price source was under the attacker’s control. It is difficult to notice because the refund calculation appears legitimate – it multiplies a gas amount by a gas price – and the contract does not emit explicit warnings when an unusually high price is used. From a user’s perspective, a participant may observe that after requesting an exit, their balance is suddenly reduced to zero or near zero, that further exits are blocked, and that they receive no refund despite having paid for the operation. This violates the fundamental business assumption that gas refunds are bounded by the actual network fee and that users retain control over their own funds. The bug belongs to the class of “untrusted parameter in financial calculation” or “price manipulation in reimbursement logic”. To remediate the flaw, the refund calculation should rely on an externally verifiable gas price oracle or enforce a maximum permissible gas price, ensuring that the refunded amount cannot exceed a reasonable ceiling and that the node does not profit from setting arbitrary tip values.

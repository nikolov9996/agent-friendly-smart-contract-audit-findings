---
id: 21552
severity: "High"
---

# ThorChain will be informed wrongly about the unsuccessful ETH transfers due to the incorrect events emissions

## Description

One of the main invariant of the protocol is:

Only valid events emitted from the Router contract itself should result in the `txInItem` parameter being populated in the `GetTxInItem` function of the `smartcontract_log_parser`.

In short, this means that all the events `ThorChain_Router` emits, should be correct.

This invariants breaks in the edge cases of the [`transferOut()`](https://github.com/code-423n4/2024-06-thorchain/blob/e3fd3c75ff994dce50d6eb66eb290d467bd494f5/ethereum/contracts/THORChain_Router.sol#L185), [`_transferOutV5()`](https://github.com/code-423n4/2024-06-thorchain/blob/e3fd3c75ff994dce50d6eb66eb290d467bd494f5/ethereum/contracts/THORChain_Router.sol#L209), [`transferOutAndCall()`](https://github.com/code-423n4/2024-06-thorchain/blob/e3fd3c75ff994dce50d6eb66eb290d467bd494f5/ethereum/contracts/THORChain_Router.sol#L261) and [`_transferOutAndCallV5()`](https://github.com/code-423n4/2024-06-thorchain/blob/e3fd3c75ff994dce50d6eb66eb290d467bd494f5/ethereum/contracts/THORChain_Router.sol#L304)

For the sake of simplicity, we will only gonna take a look at the `transferOut()` function.

`transferOut()` function is used by the vaults to transfer Native Tokens (ethers) or ERC20 Tokens to any address `to`. It first transfers the funds to the specified `to` address and then emits the `TransferOut` event for ThorChain. In case the Native Tokens transfer to the `to` address fails, it just refunds or bounce back the ethers to the vault address (`msg.sender`). Transfer to `to` address can fail often, as the function uses solidity’s `.send` to transfer the funds. If the `to` address is a contract which takes more than `2300` gas to complete the execution, then `.send` will return `false` and the ethers will be bounced back to the vault address.

The problem is, in the case when the `.send` will fail and the ethers will bounce back to the vault address, the event `TransferOut` will be wrong. As we can see, when the ethers receiver will be in vault, not the input `to` address, the `to` doesn’t get updated to the vault’s address and the function in the end emits the same `to`, ThorChain is getting informed that the ether receiver is still input `to`:

```solidity
function transferOut(address payable to, address asset, uint amount, string memory memo) public payable nonReentrant {
    uint safeAmount;
    if (asset == address(0)) {
        safeAmount = msg.value;
        bool success = to.send(safeAmount); // Send ETH.
        if (!success) {
            payable(address(msg.sender)).transfer(safeAmount); // For failure, bounce back to vault & continue.
        }
    } else {
        .....
    }
    ///@audit-issue H worng event `to` incase of the bounce back - PoC: `Should bounce back ethers but emits wrong event`
    emit TransferOut(msg.sender, to, asset, safeAmount, memo);
}
```

Technically, the ETH transfer is unsuccessful, but the ThorChain is informed that its successful and the funds are successfully transferred to the specified `to` address. Also, the `smartcontract_log_parser`’s `GetTxInItem()` function doesn’t ignore these trxs at all, as it doesn’t check if `txInItem.To` is equal to the calling vault or not.

The network believes the outbound was successful and updates the vaults accordingly, but the outbound was not successful; resulting in loss of funds for the users.

## Proof of Concept

Add this test in the `1_Router.js`:`Fund Yggdrasil, Yggdrasil Transfer Out`. Also make sure to deploy the `Navich` Contract:

```javascript
it("Should bounce back ethers but emits wrong event", async function () {
    // Contract Address which doesn't accept ethers
    let navichAddr = navich.address;

    let startBalVault = getBN(await web3.eth.getBalance(ASGARD1));
    let startBalNavich = getBN(await web3.eth.getBalance(navichAddr));

    let tx = await ROUTER1.transferOut(navichAddr, ETH, _400, "ygg+:123", {
        from: ASGARD1,
        value: _400,
    });
    
    let endBalVault = getBN(await web3.eth.getBalance(ASGARD1));
    let endBalNavich = getBN(await web3.eth.getBalance(navichAddr));
      
    // Navich Contract Balance remains same & Vault balance is unchanged as it got the refund (only gas fee cut)
    expect(BN2Str(startBalNavich)).to.equal(BN2Str(endBalNavich));
    expect(BN2Str(endBalVault)).to.not.equal(BN2Str(startBalVault) - _400);
      
    // 4 Events Logs as expected
    expect(tx.logs[0].event).to.equal("TransferOut");
    expect(tx.logs[0].args.asset).to.equal(ETH);
    expect(tx.logs[0].args.memo).to.equal("ygg+:123");
    expect(tx.logs[0].args.vault).to.equal(ASGARD1);
    expect(BN2Str(tx.logs[0].args.amount)).to.equal(_400);
      
    //🔺 Event Log of `to` address is Navich Contract instaed of the Vault (actual funds receiver) 
    expect(tx.logs[0].args.to).to.equal(navichAddr);
});

contract Navich {
    receive() external payable {
        require(msg.value == 0, "BRUH");
    }
}
```

## Recommendation

There are multiple solutions to this issue:

1. Only emit event when transfer to the target is successful (highly recommended):

```solidity
function transferOut(address payable to, address asset, uint amount, string memory memo) public payable nonReentrant {
    uint safeAmount;
    if (asset == address(0)) {
        safeAmount = msg.value;
        bool success = to.send(safeAmount); // Send ETH.
        emit TransferOut(msg.sender, to, asset, safeAmount, memo);
        if (!success) {
            payable(address(msg.sender)).transfer(safeAmount); // For failure, bounce back to vault & continue.
        }
    } else {
        _vaultAllowance[msg.sender][asset] -= amount; // Reduce allowance
        (bool success, bytes memory data) = asset.call(
            abi.encodeWithSignature("transfer(address,uint256)", to, amount)
        );
        require(success && (data.length == 0 || abi.decode(data, (bool))));
        safeAmount = amount;
        emit TransferOut(msg.sender, to, asset, safeAmount, memo);
    }
}
```

2. Simply Revert the trx upon `.send` failure.
3. Set `to` address to the vault when bounce back happens.
4. Ignore these trxs in the `smartcontract_log_parser`’s `GetTxInItem()`.
5. Use `.call` which will potentially lower the chance of failure while transferring the ethers (least recommended).

## Derived Narrative

The following field is derived content and may not be source-grounded:

The Router contract emits a TransferOut event that ThorChain uses to record an outbound transfer. In the transferOut function the contract first attempts to send native ETH to the destination address using the .send method, which forwards only 2300 gas and returns a boolean indicating success. If the send fails, the function refunds the ETH back to the calling vault but still emits the TransferOut event with the original to address unchanged. Because the event is emitted before the success check and the to field is not updated to the vault address, ThorChain parses the log and assumes the funds were successfully delivered to the intended recipient. This breaks the invariant that only events reflecting actual successful transfers should populate the txInItem structure. The bug can be triggered by sending ETH to a contract that either reverts or consumes more than 2300 gas in its fallback, causing .send to return false. The contract then bounces the ETH back to the vault, but the event still reports the original destination. From a user perspective the UI shows a successful outbound transaction, the memo and amount appear correct, yet the recipient balance remains unchanged and the vault balance is reduced only by gas, leading to apparent loss of funds. The protocol updates its accounting based on the false event, which may result in vaults being credited for funds that never left the vault, breaking accounting assumptions and potentially exposing user assets to loss. The issue was discovered during a security audit by testing a contract (named Navich) that deliberately rejects ETH, revealing that the TransferOut event reports the wrong to address while the ETH is actually returned. The problem is subtle because the transaction does not revert and no error is emitted, so standard monitoring that relies on events will not notice the failure. The vulnerability belongs to the class of premature event emission or false‑positive accounting bugs, where logs are emitted before confirming the underlying state change. A correct fix is to emit the TransferOut event only after a successful transfer, or to revert the transaction on failure, or to adjust the to field to the vault address when a bounce‑back occurs, and to ensure the log parser validates that the recorded recipient matches the actual holder of the funds.

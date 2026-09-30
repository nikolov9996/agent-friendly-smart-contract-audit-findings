---
id: 15482
severity: "High"
---

# Malicious dao owner can break lz communication

## Description

The LayerZeroImpl contract uses the NonBlockingLzApp from the LZ SDK to store all failed messages for future retries:
```solidity
function _blockingLzReceive(
    uint16 _srcChainId,
    bytes memory _srcAddress,
    uint64 _nonce,
    bytes memory payload
) internal {
    (bool success, bytes memory reason) = address(this).excessivelySafeCall(
        gasleft(),
        abi.encodeWithSelector(
            this.nonblockingLzReceive.selector,
            _srcChainId,
            _srcAddress,
            _nonce,
            payload
        )
    );
    if (!success) {
        _storeFailedMessage(_srcChainId, _srcAddress, _nonce, payload, reason);
    }
}
```
The function uses up to gasleft() gas and reads up to 150 bytes of returndata using excessivelySafeCall(). Due to the 63/64 rule, only 1/64 of the remaining gas is left for storing the failed message if nonblockingLzReceive() uses all its allocated gas. LayerZeroImpl forwards 600k gas to the endpoint:
```solidity
endpoint.send{value: msg.value}(
    _dstChainId,
    abi.encodePacked(dstCommLayer[uint16(_dstChainId)], address(this)),
    _payload,
    payable(refundAd),
    address(0x0),
    abi.encodePacked(uint16(1), uint256(600000)) // 600k
)
```
If all 63/64 gas is used, only ~9000 gas remains for storing the failed message, which is insufficient since a single zero to non-zero SSTORE costs 22.1k gas. This results in a revert in the Endpoint try/catch handling.
```solidity
try ILayerZeroReceiver(_dstAddress).lzReceive{gas: _gasLimit}(
    _srcChainId,
    _srcAddress,
    _nonce,
    _payload
) {
    // success, do nothing, end of the message delivery
} catch (bytes memory reason) {
    // revert nonce if any uncaught errors/exceptions if the ua chooses
    // the blocking mode
    storedPayload[_srcChainId][_srcAddress] = StoredPayload(uint64(_payload.length), _dstAddress, keccak256(_payload));
    emit PayloadStored(_srcChainId, _srcAddress, _dstAddress, _nonce, _payload, reason);
}
```
That is the portion that stores the payload and blocks the channel. Since gas is capped to gasLimit here, there's no risk of not leaving enough gas to store the failure in storedPayload, the Relayer is just expected to provide a small extra buffer for running the logic before and after lzReceive(). A malicious DAO owner can exploit this by setting up multiple tokens to gate the community using a large array of tokens, wasting the allocated gas. Bob, an ERC20 DAO owner, sets up an excessively large list of tokens for token gating. Bob calls crossChainBuy() to buy DAO tokens, triggering the following call stack: commLayer.sendMsg() → endpoint.send() → commLayer.lzReceive() → lzReceive() calls _nonblockingLzReceive() → factory.crossChainMint() → crossChainMint() loops through all tokens, causing an "Out Of Gas" error due to the large array. _blockingLzReceive() fails and attempts to store the failed message with insufficient gas. The revert bubbles up to the Endpoint try/catch handling, resulting in a blocked pathway.

## Proof of Concept

No poc.

## Recommendation

Limit the number of tokens that can be added by the owner, for example, to 10:
```solidity
function setupTokenGating(
    address[] calldata _tokens,
    Operator _operator,
    uint256[] calldata _value,
    address payable _daoAddress
) external payable onlyAdmins(daoDetails[_daoAddress].gnosisAddress) {
    require(_value.length == _tokens.length, "Length mismatch");
    require(_tokens.length <= 10, "Large array");
    tokenGatingDetails[_daoAddress] = TokenGatingCondition(_tokens, _operator, _value);
    daoDetails[_daoAddress].isTokenGatingApplied = true;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an out‑of‑gas denial‑of‑service condition that can be triggered by a malicious DAO owner when the contract processes an excessively large list of tokens during a cross‑chain purchase. The LayerZeroImpl contract relies on the NonBlockingLzApp pattern: when a message arrives it calls an internal _blockingLzReceive function which forwards the call to nonblockingLzReceive using the full amount of gas reported by gasleft(). Because of the EVM 63/64 rule, only one‑sixty‑fourth of the remaining gas is left for the code that runs after the call, which includes the logic that stores a failed message in case the receive call reverts. Storing a failed payload requires a zero‑to‑non‑zero SSTORE operation that costs roughly 22 k gas. When the nonblockingLzReceive function itself consumes almost all of the supplied gas – for example because it loops over a large token array supplied by the DAO owner – the leftover gas drops to around 9 k, insufficient for the storage write. The attempt to record the failed payload then reverts, and the revert propagates out of the Endpoint try/catch block, leaving the communication channel in a blocked state.

The root cause is the combination of (1) an unbounded token list that can make the cross‑chain minting logic arbitrarily expensive, and (2) the fixed gas allocation strategy of the LayerZero SDK that does not guarantee enough gas for the failure‑handling path. The issue manifests when a DAO owner deliberately adds a large number of tokens to the token‑gating configuration and then initiates a cross‑chain buy. The call stack proceeds through commLayer.sendMsg, endpoint.send, commLayer.lzReceive, lzReceive, _nonblockingLzReceive, and finally factory.crossChainMint, where the large loop triggers an out‑of‑gas error. Because the subsequent _blockingLzReceive cannot store the failed message, the endpoint’s catch block fails, and the message channel becomes permanently blocked until the state is manually corrected.

From a user’s perspective the transaction appears to be submitted but no DAO tokens are received; the user’s balance remains unchanged and the UI may show a generic “transaction failed” or “out of gas” error without indicating that the cross‑chain bridge is stuck. The protocol’s accounting assumptions – that every cross‑chain message will either succeed or be safely stored for retry – are violated, leading to potential loss of liquidity and inability to perform further cross‑chain operations.

The flaw was discovered during a security audit that examined the LayerZero integration and identified that the gas limit passed to the endpoint (600 k) combined with the 63/64 rule left an insufficient safety margin for the failure‑handling path. The problem is subtle because the SDK’s non‑blocking pattern normally masks failures, and the out‑of‑gas condition only appears when the payload processing becomes unusually heavy, which may not be exercised in normal testing.

To remediate the issue the contract should enforce a reasonable upper bound on the number of tokens that can be added to the gating list, thereby limiting the worst‑case gas consumption of the cross‑chain mint loop. Additional mitigations could include increasing the gas buffer supplied to the endpoint or redesigning the failure‑handling logic to avoid costly storage writes when gas is scarce. By constraining the token array size, the contract ensures that the non‑blocking receive always retains enough gas to store a failed message, preserving the intended retry mechanism and preventing a malicious owner from permanently blocking the communication channel.

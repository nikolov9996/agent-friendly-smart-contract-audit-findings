---
id: 25126
severity: "Medium"
---

# Signature Replay attack possible on updateWorkerDeploymentConfigWithSig() in Blueprintcore.sol which leads to users lose the funds

## Description



## Proof of Concept

## Impact

The user suffers an approximate loss of $token per replay. If replayed indefinitely (e.g., 20 times), the loss could reach 20x more, potentially draining 100% of approved funds. The attacker gains no direct funds but indirectly benefits `feeCollectionWalletAddress`, incurring only gas costs per replay. The protocol didn't have the functionality to refund this token to the respective users if this issue occurs. So anyway user is gonna lose their fund.

## Recommendation

Add a nonce to the signed message and track it per user:

```Solidity
mapping(address => uint256) public userNonces;
function updateWorkerDeploymentConfigWithSig(
    address tokenAddress,
    bytes32 projectId,
    bytes32 requestID,
    string memory updatedBase64Config,
    bytes memory signature
) public {
    bytes32 digest = keccak256(abi.encode(
        keccak256("UpdateDeploymentConfig(bytes32 projectId,string updatedBase64Config,string domain,uint256 nonce)"),
        projectId,
        keccak256(bytes(updatedBase64Config)),
        keccak256(bytes("app.crestal.network")),
        userNonces[msg.sender]
    ));
    address signerAddr = getSignerAddress(digest, signature);
    updateWorkerDeploymentConfigCommon(tokenAddress, signerAddr, projectId, requestID, updatedBase64Config);
    userNonces[signerAddr]++;
}
```

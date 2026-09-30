---
id: 3692
severity: "High"
---

# Hardcoded Router Address May Cause Token Lockup in Non-Standard Networks

## Description

This audit report provides an assessment of the contract containing the hardcoded router address for token swaps. The router address is set to "0xE592427A0AEce92De3Edee1F18E0157C05861564" and refers to a specific instance of ISwapRouter. The hardcoded router address can cause issues when deployed on networks where this address does not correspond to the appropriate Uniswap router. In such cases, tokens may become locked in the protocol indefinitely, preventing withdrawals and potentially leading to financial losses.

The contract contains the following line of code with the hardcoded router address:
```solidity
ISwapRouter public constant swapRouter = ISwapRouter(0xE592427A0AEce92De3Edee1F18E0157C05861564);
```

The hardcoded address "0xE592427A0AEce92De3Edee1F18E0157C05861564" points to a specific instance of the Uniswap Router contract. In a situation where the contract is deployed on networks with a different Uniswap router address, token swaps may not function as intended. This can result in tokens becoming locked in the protocol, leaving users unable to withdraw their tokens except for WETH and TKN (protocol token).

The presence of the hardcoded router address can lead to token lockup issues when the contract is deployed on networks with a non-standard Uniswap router. Tokens sent to the contract for swapping purposes may not be routed correctly, potentially resulting in funds being locked in the protocol forever. This can result in users losing access to their tokens and can have severe financial consequences for affected users and the protocol.

## Proof of Concept

no poc

## Recommendation

To ensure compatibility and flexibility across different networks, it is recommended to implement a more dynamic approach for setting the router address. Instead of hardcoding the router address, the contract should allow the router address to be set during deployment or provide a mechanism for the contract owner to update the router address post-deployment.

Option 1: Constructor Argument
Allow the router address to be passed as an argument during contract deployment. This way, the contract can be deployed with the appropriate router address for each network.
```solidity
constructor(address _swapRouter) {
    require(_swapRouter != address(0), "Invalid router address");
    swapRouter = ISwapRouter(_swapRouter);
}
```

Option 2: Admin Function
Implement an administrative function that allows the contract owner to update the router address after deployment. Ensure that only the contract owner can access and execute this function to prevent unauthorized changes.
```solidity
address public swapRouter;

function setSwapRouter(address _newRouter) public onlyOwner {
    require(_newRouter != address(0), "Invalid router address");
    swapRouter = ISwapRouter(_newRouter);
}
```

By implementing one of these options, the contract will be able to adapt to different networks and use the appropriate router address for token swaps, avoiding potential token lockup issues.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability consists of a hard‑coded address for the external swap router that is assumed to be a Uniswap V3 ISwapRouter instance. The contract stores the router as a constant set to 0xE592427A0AEce92De3Edee1F18E0157C05861564, which is the router address on Ethereum mainnet. When the contract is deployed on a network where this address does not point to a compatible router – for example a testnet, a side‑chain, or any environment that uses a different router deployment – the swap calls made by the contract target a contract that either does not implement the expected interface or does not exist. As a result the function that should exchange user‑supplied tokens silently fails or reverts without returning the tokens to the caller. Tokens that were transferred to the contract for swapping therefore remain locked inside the contract’s balance. From the user’s perspective the expected outcome – a successful swap and receipt of the target token – does not occur; instead the user sees their balance reduced to zero for the input token, receives no output token, and may only be able to withdraw wrapped ETH or the protocol’s native token if special withdrawal paths exist. The issue is discovered during a manual audit by CodeHawks, who noted that the address is hard‑coded and not configurable. Because the failure occurs only on networks with a mismatched router, the problem can be difficult to notice in testing that only targets the intended network; developers may assume the router works universally and therefore miss the lock‑up condition. The root cause is a configuration‑time dependency on an external contract address, a classic example of a hard‑coded dependency bug that violates the assumption that the router address is valid on every deployment environment. Exploitation does not require a malicious actor; simply deploying the contract on an unsupported network or interacting with it on such a network is sufficient to cause funds to become inaccessible. The impact is the loss of user funds that were intended for swapping, potentially leading to financial loss for both users and the protocol. The vulnerability can be mitigated by removing the constant and allowing the router address to be supplied at construction time or updated by an authorized admin, thereby ensuring that the contract always references a router that implements the expected interface on the target network.

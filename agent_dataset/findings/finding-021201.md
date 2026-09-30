---
id: 21201
severity: "High"
---

# It is possible to open insolvent position in Silo connector, due to missing check in borrow function

## Description

```solidity
[SiloConnector](https://github.com/georgiIvanov/noya-audit/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/connectors/SiloConnector.sol#L85-L107)

NOYA uses Connectors to interact with different protocols - deposit, borrow, repay, withdraw. One of the protocols is Silo through the `SiloConnector`.

In the code snippet below the `borrow` and `repay` functions of the `SiloConnector` can be seen:
    
        function borrow(address siloToken, address bToken, uint256 amount) external onlyManager nonReentrant {
            ISilo silo = ISilo(siloRepository.getSilo(siloToken));
            silo.borrow(bToken, amount);
            emit Borrow(siloToken, bToken, amount);
        }
    
    ...
    
        function repay(address siloToken, address rToken, uint256 amount) external onlyManager nonReentrant {
            ISilo silo = ISilo(siloRepository.getSilo(siloToken));
            _approveOperations(rToken, address(silo), amount);
            silo.repay(rToken, amount);
            _updateTokenInRegistry(rToken);
            if (!SolvencyV2.isSolvent(silo, address(this), minimumHealthFactor)) {
                revert IConnector_LowHealthFactor(0);
            }
            emit Repay(siloToken, rToken, amount);
        }

As can be seen in the `repay()` function there is a solvency check that reverts the transaction if the repay amount does not make to position solvent again.

However, this check is missing in the `borrow()` function which allows for a position (in Silo) to be opened that is insolvent (according to the NOYA solvency check in `SolvencyV2`) from the start.
```

## Proof of Concept

```solidity
Add the following test to `SiloConnecctor.t.sol` and run with `forge test --mt test_borrowAndRepay -vv`.
    
    function test_borrowAndRepay() public {        
        // Get value of 1 WETH in USDC
        uint256 wethPrice = chainlinkOracle.getValue(address(WETH), address(840), 1 ether);
        console.log("weth price :", wethPrice); // 2903,25841858
    
        // Deal a bit more (15%) USDC than the amount of 2 ETH. Mul by 23 and div by 10 so we deposit 115% USDC per ETH - 23/2 ETH = 1.15
        uint256 _amount = wethPrice * 23 / 100 / 10; // Divide by 100 because oracle price is 8 dec and USDC is 6. 
        console.log("USDC deposited:", _amount);
    
        _dealWhale(baseToken, address(connector), USDC_Whale, _amount);
    
        vm.startPrank(address(owner));
    
        // siloToken, deposit token, amount, open position
        connector.deposit(USDC, USDC, _amount, true);
    
        // siloToken, borrow token, amount
        connector.borrow(USDC, WETH, 2e18); // borrow 2 WETH in exchange for ~7000 USDC as collateral
    
        // Get silo repository from connector
        ISiloRepository siloRepository1 = connector.siloRepository();
    
        // Get USDC silo from silo repository
        ISilo silo = ISilo(siloRepository1.getSilo(USDC));
    
        console.log("Is Solvent: %s ", SolvencyV2.isSolvent(silo, address(connector), connector.minimumHealthFactor()));
    
        // siloToken, repay token, amount
        connector.repay(USDC, WETH, 1e18);
    
        vm.stopPrank();
    }
```

## Recommendation

```solidity
Add solvency check in the borrow function.
    
    function borrow(address siloToken, address bToken, uint256 amount) external onlyManager nonReentrant {
        ISilo silo = ISilo(siloRepository.getSilo(siloToken));
        silo.borrow(bToken, amount);
        if (!SolvencyV2.isSolvent(silo, address(this), minimumHealthFactor)) {
            revert IConnector_LowHealthFactor(0);
        }
        _updateTokenInRegistry(bToken);
        emit Borrow(siloToken, bToken, amount);
    }
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the SiloConnector contract that mediates interactions with the Silo protocol. When a manager calls the borrow function, the contract forwards the request to the underlying Silo contract but does not perform any post‑borrow solvency verification. The protocol’s own SolvencyV2 library defines a minimum health factor that must be respected to keep a position adequately collateralised. In the repay function the connector correctly checks this health factor after the repayment and reverts if the position remains insolvent, but the borrow function lacks an analogous check. As a result, a caller can open a new borrowing position that is already under‑collateralised according to the protocol’s accounting rules. The root cause is the omission of a call to SolvencyV2.isSolvent (or an equivalent health‑factor assertion) after the borrow operation. An attacker or careless user can exploit this by borrowing more assets than the deposited collateral can support, causing the connector’s internal accounting to record an insolvent position from the outset. The impact includes the possibility of under‑collateralised debt remaining on the protocol, which may later be liquidated or cause loss of funds for the connector’s users. The issue manifests when the manager invokes borrow with an amount that would breach the minimum health factor; the transaction succeeds, the user receives the borrowed tokens, but the position is flagged as insolvent when later inspected. Users see the expected borrowed amount in their wallet yet the UI or health‑factor query reports a zero or below‑threshold health factor, contradicting the expectation that borrowing is only allowed when sufficient collateral exists. The bug was discovered during a formal audit when a test case called borrow, then queried SolvencyV2.isSolvent and observed a false result, indicating that the position was already insolvent. Because the borrow function does not revert, the problem can be subtle and may only be noticed when a later operation (such as repay) triggers a solvency check and fails. To remediate, the borrow function should be amended to invoke the same solvency verification used in repay, reverting the transaction if the health factor falls below the required minimum, and updating the token registry accordingly. This change restores the invariant that all positions opened through the connector must satisfy the protocol’s collateralisation rules, preventing the creation of insolvent debt and protecting user funds.
